"""
Main entry point. Run twice a day (market open + pre-close) via GitHub
Actions. All analysis runs on the DAILY (1D) timeframe (config.TIMEFRAME).

Pipeline:
  1. Check market regime (SPY vs its own 200 SMA) - abort/flag if unhealthy
  2. Pull pre-filtered universe from FMP screener (price/cap/volume/US-only gatekeepers)
  3. Filter by analyst consensus rating
  4. Pull daily history, compute indicators
  5. Dual volume gate: BOTH current volume AND 20-day avg volume must clear
     the floor (not just one or the other)
  6. Check trend alignment, MACD recent bullish crossover, candlestick/chart
     pattern, volume spike
  7. "No chasing" gate: today's price change must be a SUBTLE 0.5%-2.5% gain,
     not an already-extended 5-8%+ move
  8. Check relative strength vs SPY (must be beating the market)
  9. Check upcoming earnings date (skip if too close - gap risk)
  10. Determine a STRATEGIC entry price (breakout level / POC / swing
      support) and the real support/resistance levels around it
  11. Build a DYNAMIC trade plan (position_sizing.py): stop at support (or
      ATR fallback), target at next resistance (or ATR fallback). Any setup
      whose resulting R:R doesn't clear MIN_RR_RATIO is rejected outright.
  12. Score the setup 0-100
  13. Rank every candidate that clears every gate, then guarantee at least
      MIN_RESULTS_PER_SCAN alerts by backfilling with the next-best scorers
  14. Skip symbols alerted within the cooldown window (no repeat alerts)
  15. Attach a TradingView chart snapshot (if chart-img.com key is configured)
  16. Send Discord alerts, plus a summary line
  17. Persist the updated alert-cooldown state
"""
import sys
import traceback
from datetime import date as date_cls

import config
import data_provider as dp
import indicators as ind
import patterns
import chart_patterns
import entry_strategy
import chart_image
import state_store
import market_context
import scoring
import position_sizing
import discord_alert as alerts


def evaluate_ticker(symbol, exchange, spy_df, rejection_counts):
    """Returns a setup dict if the ticker clears every hard gate, else None.
    Score-based filtering happens later, across the whole universe - this
    function only enforces non-negotiable rules. rejection_counts is a dict
    the caller uses to track WHERE candidates are falling out across the
    whole scan, so you can see whether e.g. the R:R gate or the day-gain
    gate is the binding constraint on a given day."""

    def reject(reason):
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        return None

    rating = dp.get_analyst_rating(symbol)
    dp.polite_sleep()
    # NOTE: analyst rating is no longer a hard gate - it's now a scoring
    # factor (see scoring.py / config.ANALYST_RATING_SCORES). This was the
    # single biggest source of rejections (44% of a full scan), and the
    # original spec said "prioritize OR filter" for analyst quality.

    df = dp.get_daily_history(symbol)
    dp.polite_sleep()
    if df is None or len(df) < config.SMA_SLOW + 5:
        return reject("insufficient_history")

    df = ind.add_all_indicators(df)
    row = df.iloc[-1]
    prev_row = df.iloc[-2]

    # ---- Part 1 gate: BOTH current volume AND average volume must clear
    # the floor (the screener's own volume filter only guarantees one). ----
    if float(row["volume"]) < config.MIN_AVG_VOLUME:
        return reject("current_volume_too_low")
    if float(row["avg_volume_20"]) < config.MIN_AVG_VOLUME:
        return reject("avg_volume_too_low")

    if not ind.trend_alignment_ok(row):
        return reject("trend_not_aligned")

    if not ind.macd_recent_bullish_crossover(df):
        return reject("no_macd_crossover")

    # Price-action trigger: a single-bar candlestick pattern OR a multi-bar
    # chart pattern breakout both qualify.
    candle_pattern = patterns.pattern_name(prev_row, row)
    chart_matches = chart_patterns.detect_chart_patterns(df)  # list of (name, level, pattern_low)

    pattern_names = ([candle_pattern] if candle_pattern else []) + [name for name, _, _ in chart_matches]
    if not pattern_names:
        return reject("no_pattern")
    pattern = " / ".join(pattern_names)

    if not ind.volume_spike_ok(row):
        return reject("no_volume_spike")

    # ---- Part 2 gate: no chasing - only subtle, early-stage moves. ----
    day_change_pct = (float(row["close"]) - float(prev_row["close"])) / float(prev_row["close"]) * 100
    if not (config.MIN_DAY_GAIN_PCT <= day_change_pct <= config.MAX_DAY_GAIN_PCT):
        return reject("day_gain_outside_band")

    # ---- Relative strength vs the market ----
    rs_outperformance, stock_return, spy_return = market_context.compute_relative_strength(df, spy_df)
    if rs_outperformance < config.RS_MIN_OUTPERFORMANCE:
        return reject("relative_strength_too_low")

    # ---- Earnings-date awareness ----
    next_earnings = None
    if config.SKIP_IF_EARNINGS_SOON:
        next_earnings = dp.get_next_earnings_date(symbol)
        dp.polite_sleep()
        if next_earnings is not None:
            days_to_earnings = (next_earnings - date_cls.today()).days
            if 0 <= days_to_earnings <= config.EARNINGS_BLACKOUT_DAYS:
                return reject("earnings_too_soon")

    # ---- Strategic entry point + real support/resistance levels ----
    entry_info = entry_strategy.determine_entry(df, chart_matches)
    entry_price = entry_info["entry_price"]

    # ---- Entry freshness check: is the calculated entry still relevant vs
    # the LIVE price? The historical data used above is EOD-only, but scans
    # run during market hours - so if the stock has already run hard
    # intraday since the last completed bar, the entry is stale and this
    # setup is effectively already gone. ----
    if config.CHECK_LIVE_PRICE_STALENESS:
        live_price = dp.get_live_quote(symbol)
        dp.polite_sleep()
        if live_price is not None:
            staleness_pct = (live_price - entry_price) / entry_price * 100
            if staleness_pct > config.MAX_ENTRY_STALENESS_PCT:
                return reject("entry_already_stale_vs_live_price")

    # ---- Part 3: dynamic trade plan (stop at support, target at next
    # resistance / measured move, ATR as last-resort fallback) + R:R
    # gatekeeper. None = reject setup. ----
    trade_plan = position_sizing.compute_dynamic_trade_plan(
        entry_price=entry_price,
        atr_value=float(row["atr"]),
        support_level=entry_info["support_level"],
        resistance_level=entry_info["resistance_level"],
        measured_move_target=entry_info["measured_move_target"],
    )
    if trade_plan is None:
        return reject("rr_below_minimum")  # failed the R:R gatekeeper (or degenerate stop)

    # ---- Position sizing (optional) ----
    sizing = (
        position_sizing.compute_position_size(entry_price, trade_plan["stop_loss"])
        if config.ENABLE_POSITION_SIZING
        else None
    )

    # ---- Composite conviction score ----
    score, score_breakdown = scoring.compute_score(
        price=float(row["close"]),
        ema50=float(row["ema50"]),
        macd=float(row["macd"]),
        macd_signal=float(row["macd_signal"]),
        volume_ratio=float(row["volume"] / row["avg_volume_20"]),
        rs_outperformance=rs_outperformance,
        num_patterns=len(pattern_names),
        rating=rating,
    )
    if score < config.ABSOLUTE_MIN_SCORE:
        return reject("score_too_low")

    return {
        "symbol": symbol,
        "exchange": exchange,
        "entry_price": trade_plan["entry_price"],
        "entry_type": entry_info["entry_type"],
        "entry_reference_level": entry_info["reference_level"],
        "day_change_pct": day_change_pct,
        "stop_loss": trade_plan["stop_loss"],
        "take_profit": trade_plan["take_profit"],
        "risk_per_share": trade_plan["risk_per_share"],
        "reward_per_share": trade_plan["reward_per_share"],
        "stop_pct": trade_plan["stop_pct"],
        "target_pct": trade_plan["target_pct"],
        "atr_pct": trade_plan["atr_pct"],
        "rr_ratio": trade_plan["rr_ratio"],
        "stop_basis": trade_plan["stop_basis"],
        "target_basis": trade_plan["target_basis"],
        "rating": rating,
        "ema50": float(row["ema50"]),
        "sma150": float(row["sma150"]),
        "sma200": float(row["sma200"]),
        "pattern": pattern,
        "volume_ratio": float(row["volume"] / row["avg_volume_20"]),
        "atr": float(row["atr"]),
        "rs_outperformance": rs_outperformance,
        "next_earnings": next_earnings,
        "sizing": sizing,
        "score": score,
        "score_breakdown": score_breakdown,
        "conviction": scoring.conviction_label(score),
    }


def run_scan():
    if not config.FMP_API_KEY:
        print("ERROR: FMP_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    if not config.DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set.", file=sys.stderr)
        sys.exit(1)
    if not config.CHART_IMG_API_KEY:
        print("NOTE: CHART_IMG_API_KEY not set - alerts will not include a chart image.")

    print("Checking FMP API key...")
    try:
        dp.check_api_key()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Timeframe: {config.TIMEFRAME}")

    # ---- Market regime check ----
    print(f"Pulling {config.REGIME_INDEX_SYMBOL} history for market regime + relative strength...")
    spy_df = dp.get_daily_history(config.REGIME_INDEX_SYMBOL)
    if spy_df is None:
        print("WARNING: could not fetch SPY history - market regime and RS checks will be skipped.", file=sys.stderr)

    if config.MARKET_REGIME_ENABLED and spy_df is not None:
        is_healthy, pct_vs_200sma, spy_close, spy_sma200 = market_context.compute_market_regime(spy_df)
        print(
            f"Market regime: {'HEALTHY' if is_healthy else 'UNHEALTHY'} "
            f"(SPY ${spy_close:.2f} vs 200SMA ${spy_sma200:.2f}, {pct_vs_200sma:+.1f}%)"
        )
        if not is_healthy and config.MARKET_REGIME_HARD_STOP:
            print("Market regime unhealthy and MARKET_REGIME_HARD_STOP is True - skipping all alerts this run.")
            alerts.send_summary(
                0, 0, [],
                note=(
                    f"⚠️ Market regime unhealthy (SPY {pct_vs_200sma:+.1f}% vs 200-day SMA) - "
                    f"no new-long alerts sent this run."
                ),
            )
            return

    print("Pulling pre-filtered universe from FMP screener...")
    universe = dp.get_screener_universe()
    print(f"Universe size after price/cap/volume/country gatekeepers: {len(universe)}")

    alert_state = state_store.load_state()

    # ---- Pass 1: evaluate every ticker, collect ALL candidates that clear
    # the hard gates (regardless of score), so we can rank across the whole
    # universe rather than just alerting the first few that happen to clear
    # the strict quality bar. rejection_counts tracks WHERE candidates fall
    # out, so you can see exactly which gate is the binding constraint. ----
    candidates = []
    rejection_counts = {}
    for i, entry in enumerate(universe, start=1):
        symbol = entry["symbol"]
        exchange = entry["exchange"]

        try:
            setup = evaluate_ticker(symbol, exchange, spy_df, rejection_counts)
        except Exception as exc:
            print(f"  [{i}/{len(universe)}] {symbol}: error - {exc}", file=sys.stderr)
            continue

        if not setup:
            continue  # reason already recorded in rejection_counts

        print(f"  [{i}/{len(universe)}] {symbol}: candidate (score {setup['score']}, R:R 1:{setup['rr_ratio']:.1f})")
        candidates.append(setup)

    print(f"Candidates clearing hard gates: {len(candidates)}")
    print("Rejection breakdown (where candidates fell out):")
    for reason, count in sorted(rejection_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {reason}: {count}")

    # ---- Pass 2: exclude anything still in cooldown ----
    eligible = []
    skipped_cooldown = []
    for setup in candidates:
        if state_store.is_in_cooldown(setup["symbol"], alert_state):
            skipped_cooldown.append(setup["symbol"])
        else:
            eligible.append(setup)

    # ---- Pass 3: rank by score, guarantee a minimum result count ----
    eligible.sort(key=lambda s: s["score"], reverse=True)
    strong = [s for s in eligible if s["score"] >= config.MIN_SIGNAL_SCORE]
    backfill = [s for s in eligible if s["score"] < config.MIN_SIGNAL_SCORE]
    final_alerts = list(strong)
    if len(final_alerts) < config.MIN_RESULTS_PER_SCAN:
        needed = config.MIN_RESULTS_PER_SCAN - len(final_alerts)
        final_alerts.extend(backfill[:needed])

    print(
        f"Eligible after cooldown: {len(eligible)} "
        f"({len(strong)} above quality bar, sending {len(final_alerts)} total after backfill)"
    )

    # ---- Send alerts ----
    matched = []
    for setup in final_alerts:
        symbol, exchange = setup["symbol"], setup["exchange"]
        print(f"Sending alert: {symbol} (score {setup['score']}, R:R 1:{setup['rr_ratio']:.1f})")
        setup["chart_url"] = chart_image.get_chart_url(symbol, exchange)
        alerts.send_alert(setup)
        state_store.mark_alerted(symbol, alert_state)
        matched.append(symbol)

    state_store.save_state(alert_state)

    alerts.send_summary(len(universe), len(matched), matched)
    print(
        f"Done. {len(matched)} alerts sent, {len(skipped_cooldown)} skipped "
        f"(cooldown), out of {len(universe)} scanned."
    )


if __name__ == "__main__":
    try:
        run_scan()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
