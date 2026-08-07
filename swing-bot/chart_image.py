"""
Generates a TradingView chart "preview" image for each alert, using
chart-img.com - a third-party service that renders real TradingView
Advanced Charts server-side and returns a hosted PNG (TradingView itself
does not expose a public image-snapshot API). Requires a chart-img.com
API key (free tier available at chart-img.com).

If no key is configured, get_chart_url() returns None and callers should
simply skip attaching an image - the rest of the bot works fine without it.
"""
import sys
import requests
import config


def _tradingview_symbol(symbol, exchange):
    """
    Builds a TradingView-style "EXCHANGE:SYMBOL" string, e.g. "NASDAQ:AAPL".
    Falls back to NASDAQ if the exchange is missing/unrecognized, since
    that's correct for the majority of US small/mid-cap tickers.
    """
    ex = (exchange or "").upper()
    if "NASDAQ" in ex:
        tv_exchange = "NASDAQ"
    elif "NYSE" in ex or "NEW YORK" in ex:
        tv_exchange = "NYSE"
    elif "AMEX" in ex or "NYSE AMERICAN" in ex:
        tv_exchange = "AMEX"
    else:
        tv_exchange = "NASDAQ"
    return f"{tv_exchange}:{symbol}"


def get_chart_url(symbol, exchange):
    """
    Returns a hosted PNG URL of the symbol's daily TradingView chart with
    the strategy's EMA/SMA trend-template overlaid, or None on any failure
    (missing key, API error, etc.) so the caller can degrade gracefully.
    """
    if not config.CHART_IMG_API_KEY:
        return None

    tv_symbol = _tradingview_symbol(symbol, exchange)
    params = {
        "symbol": tv_symbol,
        "interval": config.TIMEFRAME,  # "1D" - matches the strategy's timeframe
        "studies": config.CHART_IMG_STUDIES,
        "width": config.CHART_IMG_WIDTH,
        "height": config.CHART_IMG_HEIGHT,
        "theme": "dark",
    }
    headers = {"Authorization": f"Bearer {config.CHART_IMG_API_KEY}"}

    try:
        resp = requests.get(
            config.CHART_IMG_STORAGE_URL,
            params=params,
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("url")
    except requests.RequestException as exc:
        print(f"  {symbol}: chart image fetch failed - {exc}", file=sys.stderr)
        return None
