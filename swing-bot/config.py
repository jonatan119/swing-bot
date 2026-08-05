"""
Central configuration for the swing-trade scanner.
Tweak thresholds here without touching the scanning logic.
"""
import os

# ---- API keys / secrets (read from environment variables) ----
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
CHART_IMG_API_KEY = os.environ.get("CHART_IMG_API_KEY", "")   # optional - enables chart images

# ---- Timeframe ----
# The entire strategy (indicators, patterns, chart images) runs on the DAILY
# (1D) timeframe. FMP's historical-price-eod endpoint returns daily bars, and
# the TradingView chart image below is explicitly requested at interval=1D.
# There is currently no intraday mode - changing this is a larger change,
# not a config flag.
TIMEFRAME = "1D"

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
SCREENER_LIMIT = 3000              # max tickers to pull from FMP screener
# NOTE: FMP does not publicly document a hard ceiling for this parameter.
# Total NYSE+NASDAQ common stocks priced >$5 typically number under 3,000,
# so this comfortably covers "the whole market" for this strategy. If your
# FMP plan enforces a lower cap, the API will just return fewer rows -
# check the "Universe size after..." log line to confirm how many came back.
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

# ---- Alert deduplication ----
# Prevents the same symbol from firing a fresh alert every time you run the
# scan if it still matches. State persists across runs via a JSON file
# committed back to the repo by the GitHub Actions workflow.
STATE_FILE_PATH = "state/alerted_symbols.json"
ALERT_COOLDOWN_DAYS = 14   # don't re-alert the same symbol within this many days

# ---- Market regime filter ----
# Only send alerts when the broad market itself is healthy. The exact same
# technical setup has a meaningfully worse real-world win rate when the
# index is in a downtrend - Minervini/O'Neil-style systems stop taking new
# longs entirely in that environment, regardless of how clean an individual
# chart looks.
MARKET_REGIME_ENABLED = True
REGIME_INDEX_SYMBOL = "SPY"
# If True, suppress ALL alerts while the market is unhealthy (a single
# Discord notice explains why). If False, alerts still fire but get a
# lower score / warning tag instead of being blocked outright.
MARKET_REGIME_HARD_STOP = True

# ---- Relative Strength (RS) vs the market ----
# Core O'Neil/Minervini concept: only alert stocks actually outperforming
# the index over the medium term. A breakout in a market laggard is a much
# weaker signal than the same breakout in a leader.
RS_LOOKBACK_DAYS = 126        # ~6 months of trading days
RS_MIN_OUTPERFORMANCE = 0.0   # stock's return must beat SPY's by at least this many percentage points

# ---- Earnings-date awareness ----
# Avoids alerting right before an earnings report, where a gap can blow
# straight through an ATR-based stop no matter how clean the setup looked.
SKIP_IF_EARNINGS_SOON = True
EARNINGS_BLACKOUT_DAYS = 5

# ---- Signal scoring (0-100 conviction) ----
# Ranks *how strongly* a setup cleared every rule, instead of a flat
# pass/fail. Tune the relative importance of each factor here - they
# should sum to 1.0.
SCORE_WEIGHTS = {
    "trend": 0.25,
    "macd": 0.20,
    "volume": 0.20,
    "relative_strength": 0.20,
    "pattern_confirmation": 0.15,
}
MIN_SIGNAL_SCORE = 60          # alerts scoring below this are suppressed entirely
SCORE_HIGH_CONVICTION = 80     # >= this -> "🔥 High Conviction" label
SCORE_MEDIUM_CONVICTION = 60   # >= this -> "✅ Good Setup" label

# ---- Position sizing ----
# Edit ACCOUNT_EQUITY to your actual account size. Position size is derived
# from the ATR-based stop distance already computed for each setup, so you
# risk the same dollar amount on every trade regardless of the stock's price
# or volatility.
ENABLE_POSITION_SIZING = False   # off by default - flip to True whenever you want it back
ACCOUNT_EQUITY = 10_000.0
RISK_PER_TRADE_PCT = 1.0   # % of account equity to risk on any single trade

# ---- TradingView chart image (via chart-img.com) ----
# chart-img.com renders real TradingView charts as a hosted PNG via a simple
# REST call - this is what actually generates the "preview" image attached
# to each Discord alert. Requires a free API key from chart-img.com.
# If CHART_IMG_API_KEY is not set, alerts are sent without an image - the
# bot still works, it just skips this step.
CHART_IMG_STORAGE_URL = "https://api.chart-img.com/v1/tradingview/advanced-chart/storage"
CHART_IMG_STUDIES = [f"EMA:{EMA_FAST}", f"SMA:{SMA_MID}", f"SMA:{SMA_SLOW}"]
CHART_IMG_WIDTH = 800
CHART_IMG_HEIGHT = 450
