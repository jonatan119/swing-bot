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
MIN_MARKET_CAP = 1_500_000_000       # $1.5B floor
# User consideres sub-$1B market cap too risky/dangerous to trade - $1.5B
# keeps a safety margin above that line. Note this caps the scanned
# universe at roughly the number of US-listed companies above $1.5B
# (somewhat more than the ~1,500-2,000 that clear $2B, but still a hard
# ceiling - there's no way to scan meaningfully more while keeping a floor
# this high, short of lowering it further).
MAX_MARKET_CAP = None                # no ceiling - every mega-cap included, however large it gets
MIN_AVG_VOLUME = 500_000           # shares/day - checked against BOTH the 20-day
                                    # average AND the current day's volume (see
                                    # evaluate_ticker in scanner.py)
ACCEPTED_ANALYST_RATINGS = {"Strong Buy", "Buy"}   # kept for reference/reporting only - no longer a hard gate (see ANALYST_RATING_SCORES below)
# Analyst rating is now a SCORING factor, not a hard pass/fail gate - this
# was the single biggest source of rejections (44% of all scanned tickers
# in one run), and your original spec said "prioritize OR filter" for
# analyst quality, so this is a legitimate reading of that, not a
# loosening of a hard requirement. Strong-rated stocks still score higher
# and are more likely to clear MIN_SIGNAL_SCORE; weak/unrated stocks just
# aren't instantly killed outright.
ANALYST_RATING_SCORES = {
    "Strong Buy": 100,
    "Buy": 75,
    "Hold": 40,
    "Sell": 10,
    "Strong Sell": 0,
}
ANALYST_RATING_SCORE_IF_UNKNOWN = 30   # no coverage/unavailable - neutral-low, not a penalty or a pass
SCREENER_COUNTRY = "US"            # US-domiciled companies only (in addition to
                                    # the NYSE/NASDAQ/AMEX exchange filter below -
                                    # excludes foreign-domiciled ADRs that happen
                                    # to list on a US exchange)

# ---- 2. Trend & market structure ----
EMA_FAST = 50
SMA_MID = 150
SMA_SLOW = 200
# Small tolerance so a stock immaterially misaligned (e.g. 50 EMA 0.3% below
# 150 SMA) isn't rejected the same as one genuinely not in an uptrend. This
# is a modest loosening, not a removal - trend_not_aligned was the 2nd
# biggest source of rejections (36% of a full scan) and this template is
# core to the strategy, so it stays a hard gate, just with a bit of slack.
TREND_ALIGNMENT_TOLERANCE_PCT = 1.0

# ---- 3. Momentum triggers ----
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
# Requiring the MACD crossover on the literal single day it happens is
# extremely restrictive across a large universe - almost nothing will match
# on any given day. This widens it to "crossed within the last N sessions
# and hasn't rolled back over since" - still a real momentum signal, just
# not requiring impossible timing luck.
MACD_CROSSOVER_LOOKBACK_DAYS = 5   # widened from 3 for more candidates

# ---- 4. Volume confirmation ----
VOLUME_AVG_WINDOW = 20             # 20-day average volume
VOLUME_SPIKE_MIN = 1.10            # at least 110% of average (loosened from 120%)
VOLUME_SPIKE_MAX = 1.30            # up to 130% of average (soft upper guide)

# ---- 5. Risk management (DYNAMIC - based on real technical structure) ----
ATR_WINDOW = 14
# The ATR stop-loss multiplier now SLIDES between these two values based on
# the stock's own ATR% (see position_sizing.compute_atr_stop_multiplier),
# instead of a single fixed multiplier for every stock regardless of how
# volatile it is:
#   - Calm stocks (ATR% <= ATR_LOW_VOL_THRESHOLD_PCT) get up to 1.5x ATR of
#     room - their ATR is already small in absolute terms, so more room in
#     multiple terms doesn't create an oversized stop.
#   - Volatile stocks (ATR% >= ATR_HIGH_VOL_THRESHOLD_PCT) get down to 1.0x
#     ATR - their ATR is already large, so multiplying it further would
#     produce a disproportionately wide stop.
#   - Between the two thresholds, the multiplier interpolates linearly.
# This same sliding multiplier is used both as the ATR-based stop fallback
# (when no support level exists) AND as the minimum-distance noise floor
# (when a support level exists but sits unrealistically close to entry).
ATR_MULTIPLIER_LOW_VOL = 1.5
ATR_MULTIPLIER_HIGH_VOL = 1.0
ATR_LOW_VOL_THRESHOLD_PCT = 2.0    # ATR% at/below this -> full 1.5x multiplier
ATR_HIGH_VOL_THRESHOLD_PCT = 5.0  # ATR% at/above this -> full 1.0x multiplier

TARGET_ATR_MULTIPLIER = 3.0    # fallback target distance when no clear resistance level exists
# Hard cap on stop-loss distance as a % of entry price, regardless of what
# the technical stop (support/ATR) calculates. A pure structure-based stop
# can still get wide on volatile names - this caps worst-case downside on
# any single trade. The actual stop used is whichever is TIGHTER: the
# technical stop or this % cap.
MAX_STOP_LOSS_PCT = 5.0
STOP_BUFFER_BELOW_SUPPORT_PCT = 0.5   # stop placed slightly below support, not exactly on it

# Gatekeeper: the dynamically-calculated R:R (next resistance vs technical
# stop) must clear this ratio or the setup is rejected outright - no alert
# sent, no fallback, no exception. This replaces the old fixed 1:2 R:R.
MIN_RR_RATIO = 1.5

# ---- Entry timing (avoid chasing) ----
# Only trigger on SUBTLE, early-stage moves - a stock already up 5-8% on the
# day has already been "chased" by everyone else. Note this band needs to
# stay compatible with the volume-spike + breakout requirements elsewhere:
# a genuine breakout confirmed by 120%+ volume naturally tends to produce a
# bigger move than a quiet day, so setting this too narrow (e.g. 0.5-2.5%)
# can end up rejecting almost every real breakout rather than just the
# overextended ones. Widened to still block clearly-chased 5-8%+ moves
# without fighting the bot's own volume/pattern requirements.
MIN_DAY_GAIN_PCT = 0.2
MAX_DAY_GAIN_PCT = 5.0   # widened further for more candidates

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
# Minimum genuine depth (as a % of the neckline/breakout level) required for
# Double Bottom and Inverse Head & Shoulders to count as a real reversal
# pattern, not just two similarly-priced points found in ordinary uptrend
# noise. Without this, a normal "staircase" uptrend (higher lows along the
# 150 SMA) could falsely match as a double bottom using whatever minor local
# high sits between two small pullbacks as the "neckline" - producing a
# breakout reference far below the real overhead resistance.
MIN_PATTERN_DEPTH_PCT = 5.0

# Same idea, applied to Ascending Triangle and VCP: the base itself (top of
# resistance to bottom of the pullbacks) must span at least this % to count
# as a genuine consolidation/pause, not just ordinary day-to-day noise
# during a smooth, already-extended climb. This was the direct cause of a
# reported bad alert: ROKU's real breakout had already happened and run
# ~33% before a trivial, noise-level "triangle"/"VCP" got detected on top
# of the already-extended move.
MIN_BASE_RANGE_PCT = 8.0

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
RS_MIN_OUTPERFORMANCE = -3.0  # loosened from 0.0 - allows near-market performers, not just outperformers

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
    "trend": 0.20,
    "macd": 0.15,
    "volume": 0.15,
    "relative_strength": 0.20,
    "pattern_confirmation": 0.15,
    "analyst_rating": 0.15,
}
MIN_SIGNAL_SCORE = 60          # the "quality bar" - setups at/above this always alert
ABSOLUTE_MIN_SCORE = 30        # hard floor - never alert below this even as a fallback (loosened from 40)
MIN_RESULTS_PER_SCAN = 15      # if fewer than this clear MIN_SIGNAL_SCORE, backfill with
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
# Ascending trendline detection: how closely the recent swing lows must hug
# the fitted straight line to count as a genuine, respected trendline
# (rather than 3 arbitrary points that happen to trend upward). Tighter =
# more selective/genuine trendlines only, looser = catches more but with
# more false positives.
TRENDLINE_MAX_FIT_DEVIATION_PCT = 3.0

# ---- Entry freshness check (real-time sanity check vs stale EOD data) ----
# The bot's analysis runs on completed daily bars, but scans fire DURING
# market hours (pre-close, market-open) - so "today's close" in the data is
# actually still yesterday's close until the market shuts. If a stock has
# already run hard intraday since that last completed bar, the calculated
# entry can be well below the live price by the time you see the alert.
# This does a live quote check and rejects the setup if the current price
# has already moved too far beyond the calculated entry - i.e. "this
# opportunity is already gone, don't chase it."
CHECK_LIVE_PRICE_STALENESS = True
MAX_ENTRY_STALENESS_PCT = 4.0   # reject if live price > entry_price * (1 + this%) - loosened from 2.0
# Below MAX_ENTRY_STALENESS_PCT but above this threshold: don't reject the
# setup outright, but relabel it. A breakout entry is only meaningful if
# you're actually catching the breakout - if live price has already moved
# this far past the calculated level, the breakout already happened and
# ran; the old resistance level is now more usefully framed as a SUPPORT
# level to watch for a pullback/retest, not a price to chase into.
SUPPORT_RETEST_RECLASSIFY_PCT = 1.0
# Symmetric to MAX_ENTRY_STALENESS_PCT, but for the opposite direction:
# reject if live price has already fallen this much BELOW the calculated
# entry. A support-based entry means "price is holding near this level" -
# if it's since dropped meaningfully further, that thesis may already be
# broken, and presenting a stale entry price above where the stock
# currently trades is misleading regardless.
MAX_NEGATIVE_STALENESS_PCT = 2.0

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
