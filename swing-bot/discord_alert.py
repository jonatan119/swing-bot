"""Formats and sends swing-trade alerts to a Discord channel via webhook."""
import requests
import config


def send_alert(setup):
    """
    setup: dict with keys -
        symbol, price, rating, ema50, sma150, sma200,
        pattern, volume_ratio, stop_loss, take_profit, atr
    """
    embed = {
        "title": f"📈 Swing Setup: {setup['symbol']}",
        "color": 3066993,  # green
        "fields": [
            {"name": "Price", "value": f"${setup['price']:.2f}", "inline": True},
            {"name": "Analyst Rating", "value": setup["rating"], "inline": True},
            {"name": "Pattern", "value": setup["pattern"], "inline": True},
            {
                "name": "Trend (EMA50 / SMA150 / SMA200)",
                "value": f"${setup['ema50']:.2f} > ${setup['sma150']:.2f} > ${setup['sma200']:.2f}",
                "inline": False,
            },
            {
                "name": "Volume vs 20d Avg",
                "value": f"{setup['volume_ratio']*100:.0f}%",
                "inline": True,
            },
            {
                "name": "MACD",
                "value": "Bullish crossover ✅",
                "inline": True,
            },
            {
                "name": "Risk Management (ATR-based)",
                "value": (
                    f"Stop Loss: ${setup['stop_loss']:.2f}\n"
                    f"Take Profit: ${setup['take_profit']:.2f}\n"
                    f"R:R = 1:{config.RISK_REWARD_RATIO:.0f}"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "Automated swing-trade scan — not financial advice"},
    }

    payload = {"embeds": [embed]}
    resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()


def send_summary(num_scanned, num_matched, tickers_matched):
    lines = f"Scanned {num_scanned} tickers, {num_matched} matched all criteria."
    if tickers_matched:
        lines += "\n" + ", ".join(tickers_matched)
    payload = {"content": f"🔍 **Scan complete** — {lines}"}
    resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
