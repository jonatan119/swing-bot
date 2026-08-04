"""
Main entry point. Run twice a day (market open + close) via GitHub Actions.

Pipeline:
  1. Pull pre-filtered universe from FMP screener (price/cap/volume gatekeepers)
  2. Filter by analyst consensus rating
  3. Pull daily history, compute indicators
  4. Check trend alignment, MACD crossover, candlestick pattern, volume spike
  5. Compute ATR-based stop-loss / take-profit
  6. Send Discord alert for every match, plus a summary line
"""
import sys
import traceback

import config
import data_provider as dp
import indicators as ind
import patterns
import chart_patterns
import discord_alert as alerts


def evaluate_ticker(symbol):
    """Returns a setup dict if the ticker passes every rule, else None."""
    rating = dp.get_analyst_rating(symbol)
    dp.polite_sleep()
    if rating not in config.ACCEPTED_ANALYST_RATINGS:
        return None

    df = dp.get_daily_history(symbol)
    dp.polite_sleep()
    if df is None or len(df) < config.SMA_SLOW + 5:
        return None

    df = ind.add_all_indicators(df)
    row = df.iloc[-1]
    prev_row = df.iloc[-2]

    if not ind.trend_alignment_ok(row):
        return None

    if not ind.macd_bullish_crossover(prev_row, row):
        return None

    # Price-action trigger: a single-bar candlestick pattern OR a multi-bar
    # chart pattern breakout both qualify.
    matched_patterns = []
    candle_pattern = patterns.pattern_name(prev_row, row)
    if candle_pattern:
        matched_patterns.append(candle_pattern)
    matched_patterns.extend(chart_patterns.detect_chart_patterns(df))

    if not matched_patterns:
        return None
    pattern = " / ".join(matched_patterns)

    if not ind.volume_spike_ok(row):
        return None

    entry_price = float(row["close"])
    stop_loss, take_profit = ind.risk_management_levels(entry_price, float(row["atr"]))

    return {
        "symbol": symbol,
        "price": entry_price,
        "rating": rating,
        "ema50": float(row["ema50"]),
        "sma150": float(row["sma150"]),
        "sma200": float(row["sma200"]),
        "pattern": pattern,
        "volume_ratio": float(row["volume"] / row["avg_volume_20"]),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "atr": float(row["atr"]),
    }


def run_scan():
    if not config.FMP_API_KEY:
        print("ERROR: FMP_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    if not config.DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set.", file=sys.stderr)
        sys.exit(1)

    print("Pulling pre-filtered universe from FMP screener...")
    universe = dp.get_screener_universe()
    print(f"Universe size after price/cap/volume gatekeepers: {len(universe)}")

    matched = []
    for i, symbol in enumerate(universe, start=1):
        try:
            setup = evaluate_ticker(symbol)
        except Exception as exc:
            print(f"  [{i}/{len(universe)}] {symbol}: error - {exc}", file=sys.stderr)
            continue

        if setup:
            print(f"  [{i}/{len(universe)}] {symbol}: MATCH")
            alerts.send_alert(setup)
            matched.append(symbol)
        else:
            print(f"  [{i}/{len(universe)}] {symbol}: no match")

    alerts.send_summary(len(universe), len(matched), matched)
    print(f"Done. {len(matched)} matches out of {len(universe)} scanned.")


if __name__ == "__main__":
    try:
        run_scan()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
