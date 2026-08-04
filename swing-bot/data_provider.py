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
    Pulling pre-filtered universe from FMP screener (Requires paid plan).
    """
    print("Pulling pre-filtered universe from FMP screener...")
    params = {
        "marketCapMoreThan": 2000000000,
        "priceMoreThan": 5.0,
        "volumeMoreThan": 500000,
        "exchange": "NYSE,NASDAQ",
        "isActiveTrading": "true",
        "limit": 1000
    }
    data = _get("company-screener", params=params)
    return data

def get_historical_data(symbol):
    data = _get(f"historical-price-full/{symbol}", {"serietype": "line"})
    return data.get("historical", [])
