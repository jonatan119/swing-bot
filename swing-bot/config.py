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
MIN_MARKET_CAP = 300_000_000         # $300M floor (small-cap and up)
# Lowered from $2B since ~1,965 stocks was the actual count of $2B+ names -
# this was never a technical cap, it's just how many US stocks are that
# large. $300M opens the door to legitimate small/mid-caps too. Note most
# sub-$300M micro-caps have little/no analyst coverage anyway, so they'd
# mostly get filtered out at the analyst-rating gate regardless - this
# isn't opening the door to random penny stocks. Set to 0 to remove the
# floor entirely if you want literally everything down to $5/share.
MAX_MARKET_CAP = None                # no ceiling - every mega-cap included, however large it gets
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
# Requiring the MACD crossover on the literal single day it happens is
# extremely restrictive across a large universe - almost nothing will match
# on any given day. This widens it to "crossed within the last N sessions
# and hasn't rolled back over since" - still a real momentum signal, just
# not requiring impossible timing luck.
MACD_CROSSOVER_LOOKBACK_DAYS = 3

# ---- 4. Volume confirmation ----
VOLUME_AVG_WINDOW = 20             # 20-day average volume
VOLUME_SPIKE_MIN = 1.20            # at least 120% of average
VOLUME_SPIKE_MAX = 1.30            # up to 130% of average (soft upper guide)

# ---- 5. Risk management ----
ATR_WINDOW = 14
ATR_STOP_MULTIPLIER = 1.5
RISK_REWARD_RATIO = 2.0
# Hard cap on stop-loss distance as a % of entry price, regardless of ATR.
# A pure ATR-based stop can get very wide on volatile names (a stock with a
# 6% daily ATR would otherwise get a ~9% stop at 1.5x) - this caps the
# downside on any single trade no matter how volatile the stock is. The
# actual stop used is whichever is TIGHTER: the ATR-based stop or this %
# cap, so calm stocks still get a natural (and often tighter) ATR stop.
MAX_STOP_LOSS_PCT = 5.0

# ---- Scan universe pre-filter (keeps FMP screener call cheap & fast) ----
SCREENER_LIMIT = 10000             # max tickers to pull from FMP screener
# NOTE: this is a ceiling, not a target. Your actual universe size is driven
# by MIN_MARKET_CAP/MIN_PRICE/MIN_AVG_VOLUME below - e.g. MIN_MARKET_CAP of
# $2B alone excludes the majority of small/micro-cap US stocks, which is why
# the real "Universe size after..." log line reads ~2,000 even with this
# ceiling raised. To scan a genuinely larger slice of "the whole market",
# lower MIN_MARKET_CAP (e.g. to $300M for small-caps, or 0 for no floor).
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
MIN_SIGNAL_SCORE = 60          # the "quality bar" - setups at/above this always alert
ABSOLUTE_MIN_SCORE = 40        # hard floor - never alert below this even as a fallback
MIN_RESULTS_PER_SCAN = 5       # if fewer than this clear MIN_SIGNAL_SCORE, backfill with
                                # the next-highest scorers (down to ABSOLUTE_MIN_SCORE) so
                                # you're never left with just 1-2 alerts on a quiet day
SCORE_HIGH_CONVICTION = 80     # >= this -> "🔥 High Conviction" label
SCORE_MEDIUM_CONVICTION = 60   # >= this -> "✅ Good Setup" label

# ---- Strategic entry (support / resistance / POC) ----
# Instead of always entering at today's raw close, the bot now derives entry
# from the actual technical structure:
#   - If a chart-pattern breakout fired (cup&handle, triangle, flag, double
#     bottom, inverse H&S, VCP), entry = that pattern's specific breakout
#     level (rim/resistance/neckline) + a small buffer - i.e. a genuine
#     resistance-breakout entry, not just "whatever the close happened to be."
#   - Otherwise, entry is checked against the nearest swing support and the
#     volume-profile Point of Control (POC) - the price level with the most
#     traded volume over the lookback window, a real support/resistance
#     reference serious technical traders use.
ENTRY_BREAKOUT_BUFFER_PCT = 0.3     # entry = breakout level + this % buffer
SUPPORT_RESISTANCE_LOOKBACK = 60    # bars used to find swing support/resistance
POC_LOOKBACK = 60                   # bars used to build the volume profile
POC_BINS = 20                       # number of price buckets in the volume profile
SUPPORT_PROXIMITY_PCT = 3.0         # price must be within this % of support/POC to count as "holding" it

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
