"""
Thin wrapper around the Financial Modeling Prep (FMP) API.
Handles: universe screening, analyst ratings, historical OHLCV.

All endpoints below are FMP's current "stable" API
(https://financialmodelingprep.com/stable/...), verified against FMP's
official docs as of Aug 2026.
"""
import sys
import time
import requests
import pandas as pd

import config

BASE_URL = "https://financialmodelingprep.com/stable"


def _get(path, params=None):
    """
    GET a stable-API endpoint. Raises requests.HTTPError on non-2xx, but
    first prints a clear diagnostic (URL + status + response body) so
    failures are easy to debug from the GitHub Actions log instead of just
    showing a bare traceback.
    """
    params = dict(params or {})
    params["apikey"] = config.FMP_API_KEY
    url = f"{BASE_URL}/{path.lstrip('/')}"

    resp = requests.get(url, params=params, timeout=config.REQUEST_TIMEOUT)

    if not resp.ok:
        safe_url = resp.url.replace(config.FMP_API_KEY, "***")
        print(
            f"FMP API error: {resp.status_code} for {safe_url}\n"
            f"Response body: {resp.text[:500]}",
            file=sys.stderr,
        )
    resp.raise_for_status()
    return resp.json()


def check_api_key():
    """
    Quick sanity check called once at startup: confirms the API key is
    valid and the account can reach the stable API before we burn time
    looping over hundreds of tickers. Raises RuntimeError with a clear
    message on failure instead of a confusing mid-scan crash.
    """
    if not config.FMP_API_KEY:
        raise RuntimeError("FMP_API_KEY is not set.")
    try:
        _get("profile", params={"symbol": "AAPL"})
    except requests.HTTPError as exc:
        raise RuntimeError(
            "FMP API key check failed - the key may be invalid, expired, "
            "or lack access to the stable API on your current plan. "
            f"Original error: {exc}"
        ) from exc


def get_screener_universe():
    """
    Step 1 gatekeeper: pull a pre-filtered list of tickers directly from FMP's
    screener endpoint (market cap, price, volume, exchange) so we never have
    to loop over the *entire* US market ticker-by-ticker.
    Returns a list of dicts: {"symbol": ..., "exchange": ...}
    (exchange is carried through so we can build the correct TradingView
    "EXCHANGE:SYMBOL" string for chart images later in the pipeline.)
    """
    params = {
        "marketCapMoreThan": config.MIN_MARKET_CAP,
        "priceMoreThan": config.MIN_PRICE,
        "volumeMoreThan": config.MIN_AVG_VOLUME,
        "exchange": ",".join(config.EXCHANGES),
        "country": config.SCREENER_COUNTRY,
        "isActivelyTrading": "true",
        "limit": config.SCREENER_LIMIT,
    }
    if config.MAX_MARKET_CAP is not None:
        params["marketCapLowerThan"] = config.MAX_MARKET_CAP
    data = _get("company-screener", params=params)
    if not isinstance(data, list):
        print(f"Unexpected screener response shape: {type(data)}", file=sys.stderr)
        return []
    return [
        {"symbol": row["symbol"], "exchange": row.get("exchangeShortName") or row.get("exchange") or ""}
        for row in data
        if "symbol" in row
    ]


def get_analyst_rating(symbol):
    """
    Returns the consensus rating label (e.g. 'Strong Buy', 'Buy', 'Hold',
    'Sell', 'Strong Sell') derived from the real analyst grade distribution,
    or None if unavailable.

    Uses /stable/grades-consensus, which aggregates actual Wall Street
    analyst grades into strongBuy/buy/hold/sell/strongSell counts plus a
    computed consensus label - this is genuine analyst consensus, distinct
    from FMP's separate quant-based "ratings-snapshot" endpoint.
    """
    try:
        data = _get("grades-consensus", params={"symbol": symbol})
    except requests.RequestException as exc:
        print(f"  {symbol}: analyst rating lookup failed - {exc}", file=sys.stderr)
        return None

    if isinstance(data, list) and data:
        row = data[0]
        consensus = row.get("consensus")
        if consensus:
            return consensus
        # Fallback: derive a label ourselves from the raw counts if FMP
        # ever omits the 'consensus' field.
        strong_buy = row.get("strongBuy", 0) or 0
        buy = row.get("buy", 0) or 0
        hold = row.get("hold", 0) or 0
        sell = row.get("sell", 0) or 0
        strong_sell = row.get("strongSell", 0) or 0
        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return None
        score = (strong_buy * 5 + buy * 4 + hold * 3 + sell * 2 + strong_sell * 1) / total
        if score >= 4.5:
            return "Strong Buy"
        if score >= 3.5:
            return "Buy"
        if score >= 2.5:
            return "Hold"
        if score >= 1.5:
            return "Sell"
        return "Strong Sell"
    return None


def get_daily_history(symbol, days=None):
    """
    Returns a DataFrame with columns: date, open, high, low, close, volume
    sorted oldest -> newest. Returns None if not enough data.
    """
    days = days or config.HISTORY_DAYS
    try:
        data = _get(
            "historical-price-eod/full",
            params={"symbol": symbol},
        )
    except requests.RequestException as exc:
        print(f"  {symbol}: history lookup failed - {exc}", file=sys.stderr)
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


def get_next_earnings_date(symbol):
    """
    Returns the nearest upcoming earnings date (datetime.date) for a symbol,
    or None if unavailable/unknown. Used to avoid alerting right before an
    earnings report, where a gap can blow straight through an ATR-based stop
    regardless of how clean the technical setup looked.
    """
    from datetime import datetime, date as date_cls

    try:
        data = _get("earnings", params={"symbol": symbol})
    except requests.RequestException as exc:
        print(f"  {symbol}: earnings lookup failed - {exc}", file=sys.stderr)
        return None

    if not isinstance(data, list):
        return None

    today = date_cls.today()
    upcoming = []
    for row in data:
        raw_date = row.get("date")
        if not raw_date:
            continue
        try:
            d = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= today:
            upcoming.append(d)

    return min(upcoming) if upcoming else None


def get_live_quote(symbol):
    """
    Returns the current real-time price (float) for a symbol, or None on
    failure. Used to sanity-check that a calculated entry price isn't
    already stale - the bot's analysis runs on completed daily bars, but
    scans fire during market hours, so this is the only place actual live
    price enters the pipeline.
    """
    try:
        data = _get("quote", params={"symbol": symbol})
    except requests.RequestException as exc:
        print(f"  {symbol}: live quote lookup failed - {exc}", file=sys.stderr)
        return None

    if isinstance(data, list) and data:
        price = data[0].get("price")
        if price is not None:
            return float(price)
    return None


def polite_sleep():
    time.sleep(config.REQUEST_SLEEP)

