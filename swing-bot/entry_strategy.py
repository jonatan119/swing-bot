"""
Determines a strategic entry price instead of always using today's raw
close, and exposes the real support/resistance levels behind that decision
so position_sizing.py can build a genuinely structure-based trade plan
(stop at support, target at next resistance) rather than a flat ATR
multiple.

Three entry techniques, in priority order:

1. Breakout level - if a chart pattern fired (cup&handle, triangle, flag,
   double bottom, inverse H&S, VCP), each detector already computed its own
   rim/resistance/neckline. Entry = that level + a small buffer. The broken
   level itself becomes the new support reference (former resistance often
   acts as support on a retest).
2. Point of Control (POC) - the price level with the most traded volume
   over the lookback window (a real volume-profile support/resistance
   reference). If price is holding near/above the POC, that's a stronger
   support-based entry.
3. Swing support - the nearest prior swing low below current price, as a
   fallback support reference.

Separately, nearest_resistance() always looks for the next swing high
*above* the current price - this is what position_sizing.py uses as the
primary dynamic profit target (next resistance), with a measured-move
projection (from the matched pattern's own geometry) as a smarter
fallback than a flat ATR multiple when no resistance level exists.
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


def nearest_resistance(df, lookback=None):
    """
    Returns the nearest swing-high pivot ABOVE the current close, or None.
    Used as the dynamic profit target (the "next resistance level"). Since
    pivots are found relative to the current price, a level that's already
    been broken through (e.g. a just-cleared breakout level) is naturally
    excluded - this only returns genuinely untested resistance ahead.
    """
    lookback = lookback or config.SUPPORT_RESISTANCE_LOOKBACK
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 20:
        return None

    highs_idx, _ = chart_patterns.find_pivots(window["close"], window=4)
    current_price = window["close"].iloc[-1]
    resistances_above = [window["close"][i] for i in highs_idx if window["close"][i] > current_price]
    if not resistances_above:
        return None
    return float(min(resistances_above))  # nearest (lowest) resistance above price


def determine_entry(df, chart_pattern_matches):
    """
    Returns a dict: entry_price, entry_type, reference_level, support_level,
    resistance_level, measured_move_target.

    chart_pattern_matches: list of (name, breakout_level, pattern_low) tuples
    from chart_patterns.detect_chart_patterns().

    measured_move_target is computed as breakout_level + (breakout_level -
    pattern_low) - a real technical projection technique (the pattern's own
    height projected above the breakout), used by position_sizing.py as a
    smarter fallback target than a flat ATR multiple when no clear next
    resistance level exists.
    """
    current_close = float(df["close"].iloc[-1])
    resistance_level = nearest_resistance(df)

    measured_move_target = None
    if chart_pattern_matches:
        # Use the pattern with the largest measured-move projection - i.e.
        # the deepest/tallest base, which classically projects the biggest
        # (and most structurally justified) move.
        projections = [level + (level - low) for _, level, low in chart_pattern_matches]
        measured_move_target = max(projections)

    # 1. Breakout entry - use the highest confirmed breakout level (most
    # conservative: the hardest resistance to clear) plus a small buffer.
    # The broken level itself becomes the new support reference.
    if chart_pattern_matches:
        breakout_level = max(level for _, level, _ in chart_pattern_matches)
        entry_price = breakout_level * (1 + config.ENTRY_BREAKOUT_BUFFER_PCT / 100)
        return {
            "entry_price": entry_price,
            "entry_type": "Resistance Breakout",
            "reference_level": breakout_level,
            "support_level": breakout_level,
            "resistance_level": resistance_level,
            "measured_move_target": measured_move_target,
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
                "support_level": poc,
                "resistance_level": resistance_level,
                "measured_move_target": measured_move_target,
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
                "support_level": support,
                "resistance_level": resistance_level,
                "measured_move_target": measured_move_target,
            }

    # 4. Fallback - no clean S/R confluence found near the current price.
    return {
        "entry_price": current_close,
        "entry_type": "Unconfirmed (no clear S/R confluence)",
        "reference_level": None,
        "support_level": support,
        "resistance_level": resistance_level,
        "measured_move_target": measured_move_target,
    }
