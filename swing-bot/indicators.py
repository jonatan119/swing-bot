"""
Technical indicator calculations, built on pandas_ta.
All functions take/return pandas Series or scalars derived from a
DataFrame with columns: open, high, low, close, volume.
"""
import pandas_ta as ta
import config


def add_all_indicators(df):
    """Mutates and returns df with every indicator column the strategy needs."""
    df = df.copy()

    df["ema50"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["sma150"] = ta.sma(df["close"], length=config.SMA_MID)
    df["sma200"] = ta.sma(df["close"], length=config.SMA_SLOW)

    macd = ta.macd(
        df["close"],
        fast=config.MACD_FAST,
        slow=config.MACD_SLOW,
        signal=config.MACD_SIGNAL,
    )
    # pandas_ta names columns like MACD_12_26_9 / MACDs_12_26_9
    macd_col = f"MACD_{config.MACD_FAST}_{config.MACD_SLOW}_{config.MACD_SIGNAL}"
    signal_col = f"MACDs_{config.MACD_FAST}_{config.MACD_SLOW}_{config.MACD_SIGNAL}"
    df["macd"] = macd[macd_col]
    df["macd_signal"] = macd[signal_col]

    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=config.ATR_WINDOW)

    df["avg_volume_20"] = df["volume"].rolling(config.VOLUME_AVG_WINDOW).mean()

    return df


def trend_alignment_ok(row):
    """
    50 EMA > 150 SMA > 200 SMA, and price > 50 EMA - with a small tolerance
    buffer (config.TREND_ALIGNMENT_TOLERANCE_PCT) so a stock that's
    immaterially misaligned (e.g. 50 EMA 0.3% below 150 SMA) isn't rejected
    the same as one that's genuinely not in an uptrend. This is a small
    loosening, not a removal - the trend template is core to the strategy.
    """
    if any(pd_isna(row[c]) for c in ("ema50", "sma150", "sma200")):
        return False
    tol = 1 - (config.TREND_ALIGNMENT_TOLERANCE_PCT / 100)
    return (
        row["close"] > row["ema50"] * tol
        and row["ema50"] > row["sma150"] * tol
        and row["sma150"] > row["sma200"] * tol
    )


def macd_bullish_crossover(prev_row, row):
    """True only on the exact bar where MACD crosses above its signal line."""
    if any(pd_isna(v) for v in (prev_row["macd"], prev_row["macd_signal"], row["macd"], row["macd_signal"])):
        return False
    return prev_row["macd"] <= prev_row["macd_signal"] and row["macd"] > row["macd_signal"]


def macd_recent_bullish_crossover(df, lookback_days=None):
    """
    True if MACD crossed above its signal line at any point in the last
    `lookback_days` sessions AND is still above the signal line today.

    Requiring the crossover on the literal single day (macd_bullish_crossover
    above) is extremely restrictive across a large universe - most days,
    almost nothing will have crossed on that exact bar. This widens the
    window to "recently turned bullish and hasn't rolled back over yet",
    which is still a meaningful momentum signal but yields a realistic
    number of daily candidates instead of near-zero.
    """
    lookback_days = lookback_days or config.MACD_CROSSOVER_LOOKBACK_DAYS
    if len(df) < lookback_days + 2:
        return False

    last = df.iloc[-1]
    if pd_isna(last["macd"]) or pd_isna(last["macd_signal"]):
        return False
    if last["macd"] <= last["macd_signal"]:
        return False  # not currently bullish - rolled back over already

    for offset in range(0, lookback_days):
        curr = df.iloc[-1 - offset]
        prev = df.iloc[-2 - offset]
        if macd_bullish_crossover(prev, curr):
            return True
    return False


def volume_spike_ok(row):
    if pd_isna(row["avg_volume_20"]) or row["avg_volume_20"] == 0:
        return False
    ratio = row["volume"] / row["avg_volume_20"]
    return ratio >= config.VOLUME_SPIKE_MIN


def atr_pct(entry_price, atr_value):
    """ATR expressed as a % of price - simple helper used for display and
    for the dynamic stop/target calculations in position_sizing.py."""
    return atr_value / entry_price * 100


def pd_isna(value):
    import pandas as pd
    return pd.isna(value)
