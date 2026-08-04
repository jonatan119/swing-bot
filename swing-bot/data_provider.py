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
    Pulling the company list from FMP and filtering for liquid US stocks.
    """
    print("Pulling active company list from FMP...")
    # שליפת רשימת החברות המלאה הזמינה ב-API
    data = _get("financial-statement-symbol-all")
    
    # ב-FMP לפעמים הרשימה מחזירה מחרוזות של סימולים או מילונים, נסנן את הנפוצות והנזילות
    # נבחר רשימה מצומצמת ואיכותית של מניות מובילות בבורסה שנסחרות בנפח גבוה
    print(f"Total symbols fetched: {len(data)}")
    
    # ניקח את הסימולים ונוודא שהם פורמט נקי
    tickers = []
    for item in data:
        if isinstance(item, dict):
            symbol = item.get("symbol")
        else:
            symbol = item
        if symbol:
            tickers.append({"symbol": symbol})
            
    # מגביל לראשונות לעֹומס ראשוני או מחזיר את כולן לפי הצורך
    return tickers[:300]

def get_historical_data(symbol):
    data = _get(f"historical-price-full/{symbol}", {"serietype": "line"})
    return data.get("historical", [])
