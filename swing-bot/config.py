"""
Central configuration for the swing-trade scanner.
Tweak thresholds here without touching the scanning logic.
"""
import os

# ---- API keys / secrets (read from environment variables) ----
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# ---- 1. Fundamental & liquidity gatekeepers ----
MIN_PRICE = 5.0
MIN_MARKET_CAP = 2_000_000_000     # $2B
MIN_AVG_VOLUME = 500_000           # shares/day
ACCEPTED_ANALYST_RATINGS = {"Strong Buy", "Buy"}

# ---- 2. Trend & market structure ----
EMA_FAST = 50
SMA_MID = 150
SMA_SLOW = 200

# ---- 3. Momentum triggers ----
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ---- 4. Volume confirmation ----
VOLUME_AVG_WINDOW = 20             # 20-day average volume
VOLUME_SPIKE_MIN = 1.20            # at least 120% of average
VOLUME_SPIKE_MAX = 1.30            # up to 130% of average (soft upper guide)

# ---- 5. Risk management ----
ATR_WINDOW = 14
ATR_STOP_MULTIPLIER = 1.5
RISK_REWARD_RATIO = 2.0

# ---- Scan universe pre-filter (keeps FMP screener call cheap & fast) ----
SCREENER_LIMIT = 1000              # max tickers to pull from FMP screener
EXCHANGES = ["NYSE", "NASDAQ", "AMEX"]

# ---- Historical data window needed to compute 200 SMA + MACD + ATR safely ----
HISTORY_DAYS = 260

# ---- Chart pattern detection (in addition to single-bar candlestick patterns) ----
# A setup qualifies if it shows a bullish candlestick pattern (engulfing/hammer)
# OR any one of the chart patterns below breaking out. Comment out any pattern
# name to disable it without touching detection code.
ENABLED_CHART_PATTERNS = {
    "Cup and Handle",
    "Ascending Triangle",
    "Bull Flag",
    "Double Bottom",
    "Inverse Head and Shoulders",
    "VCP Breakout",
}

# ---- Networking ----
REQUEST_TIMEOUT = 15
REQUEST_SLEEP = 0.25   # polite delay between per-ticker API calls
