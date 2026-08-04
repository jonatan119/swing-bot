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
    Pulling the official stock list from FMP and filtering for liquid US stocks.
    """
    print("Pulling official stock list from FMP...")
    data = _get("stock/list")
    
    print(f"Total symbols fetched: {len(data)}")
    
    # סינון מניות אמריקאיות נזילות (NYSE ו-NASDAQ) עם מחיר ונפח סביר
    filtered = []
    for stock in data:
        exchange = stock.get("exchange", "")
        price = stock.get("price", 0) or 0
        
        if exchange in ["New York Stock Exchange", "NASDAQ Global Select", "NasdaqGM", "NasdaqCM", "NYSE American"]:
            if price > 5.0:
                filtered.append({"symbol": stock.get("symbol")})
                
    print(f"Found {len(filtered)} matching stocks after filtering.")
    return filtered[:300] # מגביל ל-300 הראשונות כדי שהריצה תהיה חלקה ומהירה

def get_historical_data(symbol):
    data = _get(f"historical-price-full/{symbol}", {"serietype": "line"})
    return data.get("historical", [])
