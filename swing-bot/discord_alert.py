"""Formats and sends swing-trade alerts to a Discord channel via webhook."""
import requests
import config


def send_alert(setup):
    """
    setup: dict with keys -
        symbol, exchange, entry_price, entry_type, entry_reference_level,
        day_change_pct, rating, ema50, sma150, sma200, pattern, volume_ratio,
        stop_loss, take_profit, risk_per_share, reward_per_share, stop_pct,
        target_pct, atr, atr_pct, rr_ratio, stop_basis, target_basis,
        rs_outperformance, next_earnings, sizing, score, score_breakdown,
        conviction, current_price, live_price, current_volume, avg_volume,
        chart_url (optional - TradingView chart snapshot PNG)
    """
    sizing = setup.get("sizing")

    entry_ref = (
        f" (ref: ${setup['entry_reference_level']:.2f})"
        if setup.get("entry_reference_level") is not None
        else ""
    )

    fields = [
        {
            "name": "🎯 Trade Plan",
            "value": (
                f"**Entry:** ${setup['entry_price']:.2f} — {setup['entry_type']}{entry_ref}\n"
                f"**Day Change:** {setup['day_change_pct']:+.1f}% (early-stage, not chasing)\n"
                f"**Stop Loss:** ${setup['stop_loss']:.2f}  ({setup['stop_pct']:+.1f}%)  "
                f"[basis: {setup['stop_basis']}"
                + (f", {setup['atr_multiplier_used']}x ATR" if "ATR" in setup['stop_basis'] else "")
                + "]\n"
                f"**Potential of:** ${setup['take_profit']:.2f}  ({setup['target_pct']:+.1f}%)  "
                f"[basis: {setup['target_basis']}]\n"
                f"**Risk/Share:** ${setup['risk_per_share']:.2f}  |  "
                f"**Reward/Share:** ${setup['reward_per_share']:.2f}  "
                f"(R:R = 1:{setup['rr_ratio']:.1f})"
            ),
            "inline": False,
        },
    ]

    if sizing:
        fields.append({
            "name": "💰 Position Size",
            "value": (
                f"**Shares:** {sizing['shares']}  |  **Risking:** ${sizing['dollar_risk']:.0f} "
                f"({config.RISK_PER_TRADE_PCT:.1f}% of ${config.ACCOUNT_EQUITY:,.0f} account)\n"
                f"**Position Value:** ${sizing['position_value']:,.0f} "
                f"({sizing['position_pct_of_equity']:.1f}% of equity)"
            ),
            "inline": False,
        })

    earnings_text = (
        f"⚠️ Earnings on {setup['next_earnings'].isoformat()}"
        if setup.get("next_earnings")
        else "None scheduled soon"
    )

    fields.extend([
        {
            "name": "📊 Live vs. Signal-Day Price",
            "value": (
                f"**Current Price:** ${setup['live_price']:.2f}\n" if setup.get("live_price") else ""
            ) + (
                f"**Signal-Day Close:** ${setup['current_price']:.2f}\n"
                f"**Current Volume:** {setup['current_volume']:,.0f}\n"
                f"**Avg Volume (20d):** {setup['avg_volume']:,.0f}"
            ),
            "inline": False,
        },
        {"name": "Analyst Rating", "value": setup["rating"] or "No coverage", "inline": True},
        {"name": "Pattern", "value": setup["pattern"], "inline": True},
        {"name": "Volume vs 20d Avg", "value": f"{setup['volume_ratio']*100:.0f}%", "inline": True},
        {
            "name": "Trend (EMA50 / SMA150 / SMA200)",
            "value": f"${setup['ema50']:.2f} > ${setup['sma150']:.2f} > ${setup['sma200']:.2f}",
            "inline": False,
        },
        {"name": "MACD", "value": "Bullish (recent crossover)", "inline": True},
        {"name": "ATR (14)", "value": f"${setup['atr']:.2f}  ({setup['atr_pct']:.1f}%)", "inline": True},
        {"name": "RS vs SPY (6mo)", "value": f"{setup['rs_outperformance']:+.1f} pts", "inline": True},
        {"name": "Earnings Risk", "value": earnings_text, "inline": True},
    ])

    embed = {
        "title": f"{setup['conviction']} — {setup['symbol']}  (Score: {setup['score']}/100)",
        "color": 3066993,  # green
        "fields": fields,
        "footer": {"text": "Automated swing-trade scan — not financial advice"},
    }

    if setup.get("chart_url"):
        embed["image"] = {"url": setup["chart_url"]}

    payload = {"embeds": [embed]}
    resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()


def send_summary(num_scanned, num_matched, tickers_matched, note=None):
    lines = f"Scanned {num_scanned} tickers, {num_matched} alerted."
    if tickers_matched:
        lines += "\n" + ", ".join(tickers_matched)
    content = f"🔍 **Scan complete** — {lines}"
    if note:
        content += f"\n\n{note}"

    payload = {"content": content}
    resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
