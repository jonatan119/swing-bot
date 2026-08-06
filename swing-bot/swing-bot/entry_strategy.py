"""
Determines a strategic entry price instead of always using today's raw
close. Three techniques, in priority order:

1. Breakout level - if a chart pattern fired (cup&handle, triangle, flag,
   double bottom, inverse H&S, VCP), each detector already computed its own
   rim/resistance/neckline. Entry = that level + a small buffer, i.e. a
   genuine resistance-breakout entry.
2. Point of Control (POC) - the price level with the most traded volume
   over the lookback window (a real volume-profile support/resistance
   reference). If price is holding near/above the POC, that's a stronger
   support-based entry.
3. Swing support - the nearest prior swing low below current price, as a
   fallback support reference.

If none of these are within a reasonable distance of the current price, the
bot falls back to the raw close, but tags the entry as "unconfirmed" so
that's visible in the alert rather than silently assumed.
"""
import chart_patterns
import config


def compute_poc(df, lookback=None, bins=None):
    """
    Builds a simple volume profile over the lookback window and returns the
    Point of Control - the price bucket with the highest total volume.
    """
    lookback = lookback or config.POC_LOOKBACK
    bins = bins or config.POC_BINS
    window = df.tail(lookback)
    if len(window) < 10:
        return None

    lo, hi = window["low"].min(), window["high"].max()
    if hi <= lo:
        return None

    bin_edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    bin_volume = [0.0] * bins

    for _, row in window.iterrows():
        # Approximate: assign the bar's volume to the bin containing its close.
        price = row["close"]
        bin_idx = min(int((price - lo) / (hi - lo) * bins), bins - 1)
        bin_volume[bin_idx] += row["volume"]

    poc_bin = max(range(bins), key=lambda i: bin_volume[i])
    poc_price = (bin_edges[poc_bin] + bin_edges[poc_bin + 1]) / 2
    return float(poc_price)


def nearest_support(df, lookback=None):
    """Returns the nearest swing-low pivot below the current close, or None."""
    lookback = lookback or config.SUPPORT_RESISTANCE_LOOKBACK
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 20:
        return None

    _, lows_idx = chart_patterns.find_pivots(window["close"], window=4)
    current_price = window["close"].iloc[-1]
    supports_below = [window["close"][i] for i in lows_idx if window["close"][i] < current_price]
    if not supports_below:
        return None
    return float(max(supports_below))  # nearest (highest) support below price


def determine_entry(df, chart_pattern_matches):
    """
    Returns a dict: entry_price, entry_type, reference_level (the S/R or POC
    value that justified the entry, for display).

    chart_pattern_matches: list of (name, breakout_level) tuples from
    chart_patterns.detect_chart_patterns().
    """
    current_close = float(df["close"].iloc[-1])

    # 1. Breakout entry - use the highest confirmed breakout level (most
    # conservative: the hardest resistance to clear) plus a small buffer.
    if chart_pattern_matches:
        breakout_level = max(level for _, level in chart_pattern_matches)
        entry_price = breakout_level * (1 + config.ENTRY_BREAKOUT_BUFFER_PCT / 100)
        return {
            "entry_price": entry_price,
            "entry_type": "Resistance Breakout",
            "reference_level": breakout_level,
        }

    # 2. POC support check
    poc = compute_poc(df)
    if poc is not None:
        distance_pct = (current_close - poc) / poc * 100
        if 0 <= distance_pct <= config.SUPPORT_PROXIMITY_PCT:
            return {
                "entry_price": current_close,
                "entry_type": "POC Support Hold",
                "reference_level": poc,
            }

    # 3. Swing support check
    support = nearest_support(df)
    if support is not None:
        distance_pct = (current_close - support) / support * 100
        if 0 <= distance_pct <= config.SUPPORT_PROXIMITY_PCT:
            return {
                "entry_price": current_close,
                "entry_type": "Support Bounce",
                "reference_level": support,
            }

    # 4. Fallback - no clean S/R confluence found near the current price.
    return {
        "entry_price": current_close,
        "entry_type": "Unconfirmed (no clear S/R confluence)",
        "reference_level": None,
    }
