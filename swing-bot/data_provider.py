import time
import requests
import pandas as pd

import config

BASE_URL = "https://financialmodelingprep.com"


def _get(path, params=None):
    params = params or {}
    params["apikey"] = config.FMP_API_KEY
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_screener_universe():
    """
    Step 1 gatekeeper: pull a pre-filtered list of tickers directly from FMP's
    screener endpoint (market cap, price, volume, exchange) so we never have
    to loop over the *entire* US market ticker-by-ticker.
    Returns a list of ticker symbols.
    """
    params = {
        "marketCapMoreThan": config.MIN_MARKET_CAP,
        "priceMoreThan": config.MIN_PRICE,
        "volumeMoreThan": config.MIN_AVG_VOLUME,
        "exchange": ",".join(config.EXCHANGES),
        "isActivelyTrading": "true",
        "limit": config.SCREENER_LIMIT,
    }
    data = _get("/stable/company-screener", params=params)
    if not isinstance(data, list):
        return []
    return [row["symbol"] for row in data if "symbol" in row]


def get_analyst_rating(symbol):
    """
    Returns the consensus rating label (e.g. 'Strong Buy', 'Buy', 'Hold', 'Sell')
    or None if unavailable.
    """
    try:
        data = _get("/stable/ratings-snapshot", params={"symbol": symbol})
        if isinstance(data, list) and data:
            return data[0].get("ratingRecommendation")
    except requests.RequestException:
        return None
    return None


def get_daily_history(symbol, days=None):
    """
    Returns a DataFrame with columns: date, open, high, low, close, volume
    sorted oldest -> newest. Returns None if not enough data.
    """
    days = days or config.HISTORY_DAYS
    try:
        data = _get(
            "/stable/historical-price-eod/full",
            params={"symbol": symbol, "serietype": "line"},
        )
    except requests.RequestException:
        return None

    rows = data if isinstance(data, list) else data.get("historical", [])
    if not rows or len(rows) < days:
        return None

    df = pd.DataFrame(rows)
    if df.empty or "date" not in df.columns:
        return None

    df = df.sort_values("date").tail(days).reset_index(drop=True)
    needed = {"open", "high", "low", "close", "volume"}
    if not needed.issubset(df.columns):
        return None

    return df[["date", "open", "high", "low", "close", "volume"]]


def polite_sleep():
    time.sleep(config.REQUEST_SLEEP)
