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
    Pulling the active stock universe from FMP and filtering for liquid US stocks.
    """
    print("Pulling stock universe from FMP...")
    # שליפת כל המניות הפעילות בבורסות ארה"ב
    data = _get("stock-screener", {"exchange": "NYSE,NASDAQ", "limit": 2000})
    
    # סינון פנימי בקוד לוודא שהן עומדות בקריטריונים (שווי שוק, מחיר ונפח)
    filtered = []
    for stock in data:
        mcap = stock.get("marketCap", 0) or 0
        price = stock.get("price", 0) or 0
        vol = stock.get("volume", 0) or 0
        
        if mcap > 2000000000 and price > 5.0 and vol > 500000:
            filtered.append(stock)
            
    print(f"Found {len(filtered)} stocks matching criteria after local filtering.")
    return filtered

def get_historical_data(symbol):
    data = _get(f"historical-price-full/{symbol}", {"serietype": "line"})
    return data.get("historical", [])
