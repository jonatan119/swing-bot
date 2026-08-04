import os
import requests

API_KEY = os.getenv("FMP_API_KEY")
BASE_URL = "https://financialmodelingprep.com/stable"

def _get(endpoint, params=None):
    if params is None:
        params = {}
    params["apikey"] = API_KEY
    url = f"{BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def get_screener_universe():
    """
    Returning a fixed list of liquid US tickers for the free tier,
    bypassing the paid screener endpoint limit.
    """
    print("Using free-tier predefined ticker list...")
    # רשימת מניות לדוגמה שנסחרות בנפח גבוה ומתאימות לשורט/לונג סווינג
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "PLTR", "CVS", "TGT", "AMD", "NFLX"]
    return [{"symbol": ticker} for ticker in tickers]

def get_historical_data(symbol):
    data = _get(f"historical-price-full/{symbol}", {"serietype": "line"})
    return data.get("historical", [])
