"""Formats and sends swing-trade alerts to a Discord channel via webhook."""
import requests
import config


def send_alert(setup):
    """
    setup: dict with keys -
        symbol, exchange, entry_price, rating, ema50, sma150, sma200,
        pattern, volume_ratio, stop_loss, take_profit,
        risk_per_share, reward_per_share, stop_pct, target_pct, atr,
        rs_outperformance, next_earnings, sizing, score, score_breakdown,
        conviction, chart_url (optional - TradingView chart snapshot PNG)
    """
    sizing = setup.get("sizing")

    fields = [
        {
            "name": "🎯 Trade Plan",
            "value": (
                f"**Entry:** ${setup['entry_price']:.2f}\n"
                f"**Stop Loss:** ${setup['stop_loss']:.2f}  ({setup['stop_pct']:+.1f}%)\n"
                f"**Take Profit:** ${setup['take_profit']:.2f}  ({setup['target_pct']:+.1f}%)\n"
                f"**Risk/Share:** ${setup['risk_per_share']:.2f}  |  "
                f"**Reward/Share:** ${setup['reward_per_share']:.2f}  "
                f"(R:R = 1:{config.RISK_REWARD_RATIO:.0f})"
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
        {"name": "Analyst Rating", "value": setup["rating"], "inline": True},
        {"name": "Pattern", "value": setup["pattern"], "inline": True},
        {"name": "Volume vs 20d Avg", "value": f"{setup['volume_ratio']*100:.0f}%", "inline": True},
        {
            "name": "Trend (EMA50 / SMA150 / SMA200)",
            "value": f"${setup['ema50']:.2f} > ${setup['sma150']:.2f} > ${setup['sma200']:.2f}",
            "inline": False,
        },
        {"name": "MACD", "value": "Bullish crossover ✅", "inline": True},
        {"name": "ATR (14)", "value": f"${setup['atr']:.2f}", "inline": True},
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
    lines = f"Scanned {num_scanned} tickers, {num_matched} matched all criteria."
    if tickers_matched:
        lines += "\n" + ", ".join(tickers_matched)
    content = f"🔍 **Scan complete** — {lines}"
    if note:
        content += f"\n\n{note}"
    payload = {"content": content}
    resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
