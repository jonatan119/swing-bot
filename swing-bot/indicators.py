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
    """50 EMA > 150 SMA > 200 SMA, and price > 50 EMA."""
    if any(pd_isna(row[c]) for c in ("ema50", "sma150", "sma200")):
        return False
    return (
        row["close"] > row["ema50"] > row["sma150"] > row["sma200"]
    )


def macd_bullish_crossover(prev_row, row):
    """True only on the bar where MACD crosses above its signal line."""
    if any(pd_isna(v) for v in (prev_row["macd"], prev_row["macd_signal"], row["macd"], row["macd_signal"])):
        return False
    return prev_row["macd"] <= prev_row["macd_signal"] and row["macd"] > row["macd_signal"]


def volume_spike_ok(row):
    if pd_isna(row["avg_volume_20"]) or row["avg_volume_20"] == 0:
        return False
    ratio = row["volume"] / row["avg_volume_20"]
    return ratio >= config.VOLUME_SPIKE_MIN


def risk_management_levels(entry_price, atr_value):
    """
    Returns a dict with the full trade plan:
    entry_price, stop_loss, take_profit, risk_per_share, reward_per_share,
    stop_pct (% below entry), target_pct (% above entry).
    """
    stop_loss = entry_price - config.ATR_STOP_MULTIPLIER * atr_value
    risk_per_share = entry_price - stop_loss
    reward_per_share = config.RISK_REWARD_RATIO * risk_per_share
    take_profit = entry_price + reward_per_share

    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "stop_pct": (stop_loss - entry_price) / entry_price * 100,
        "target_pct": (take_profit - entry_price) / entry_price * 100,
    }


def pd_isna(value):
    import pandas as pd
    return pd.isna(value)
