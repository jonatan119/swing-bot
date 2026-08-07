"""
Lightweight candlestick pattern detection, implemented directly on OHLC
values (no TA-Lib dependency, keeps deployment simple on GitHub Actions).
"""


def is_bullish_engulfing(prev_row, row):
    prev_bearish = prev_row["close"] < prev_row["open"]
    curr_bullish = row["close"] > row["open"]
    engulfs = row["open"] <= prev_row["close"] and row["close"] >= prev_row["open"]
    return prev_bearish and curr_bullish and engulfs


def is_bullish_hammer(row):
    body = abs(row["close"] - row["open"])
    candle_range = row["high"] - row["low"]
    if candle_range == 0:
        return False

    lower_wick = min(row["open"], row["close"]) - row["low"]
    upper_wick = row["high"] - max(row["open"], row["close"])

    small_body = body <= 0.35 * candle_range
    long_lower_wick = lower_wick >= 2 * body if body > 0 else lower_wick >= 0.5 * candle_range
    small_upper_wick = upper_wick <= 0.15 * candle_range

    return small_body and long_lower_wick and small_upper_wick


def bullish_pattern_present(prev_row, row):
    return is_bullish_engulfing(prev_row, row) or is_bullish_hammer(row)


def pattern_name(prev_row, row):
    names = []
    if is_bullish_engulfing(prev_row, row):
        names.append("Bullish Engulfing")
    if is_bullish_hammer(row):
        names.append("Bullish Hammer")
    return " + ".join(names) if names else None
