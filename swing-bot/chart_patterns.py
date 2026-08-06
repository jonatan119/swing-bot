"""
Multi-bar chart pattern detection using swing-point (pivot) geometry.
These are heuristic, rule-based approximations of classic technical
patterns -- not a guarantee of the textbook shape, but tuned to catch
the setups swing traders consider high win-rate continuation/reversal
signals. No external TA library required.

Each detector returns (breakout_level, pattern_low) on a match, or None
otherwise:
  - breakout_level: the resistance/rim/neckline that was cleared
  - pattern_low: the structural base of the pattern (cup bottom, pole
    start, head, etc.) - used to compute a measured-move price target
    (breakout_level + (breakout_level - pattern_low)), a real technique
    for projecting a target from the pattern's own geometry rather than
    guessing or relying only on the next swing high.

All functions expect a DataFrame with columns: open, high, low, close, volume
sorted oldest -> newest, and operate on the trailing window of bars.
"""
import config


def _dedupe_run(indices, min_gap):
    """Collapses runs of adjacent pivot indices (e.g. a flat top/bottom that
    gets flagged at every bar) down to a single representative index each."""
    if not indices:
        return []
    deduped = [indices[0]]
    for idx in indices[1:]:
        if idx - deduped[-1] <= min_gap:
            continue  # part of the same plateau, skip
        deduped.append(idx)
    return deduped


def find_pivots(series, window=5):
    """
    Returns (high_idx, low_idx): lists of integer positions that are local
    swing highs / lows, i.e. higher/lower than `window` bars on both sides.
    Adjacent duplicate detections (flat tops/bottoms) are collapsed to one
    point each so downstream strict-inequality checks behave sensibly.
    """
    highs, lows = [], []
    n = len(series)
    for i in range(window, n - window):
        seg = series[i - window : i + window + 1]
        if series[i] == max(seg):
            highs.append(i)
        if series[i] == min(seg):
            lows.append(i)
    return _dedupe_run(highs, window), _dedupe_run(lows, window)


def _pct(a, b):
    """Percent difference of a relative to b."""
    if b == 0:
        return 0
    return (a - b) / b


# ---------------------------------------------------------------- Cup & Handle
def detect_cup_and_handle(df, lookback=130, handle_max_len=15):
    """
    Classic O'Neil cup-and-handle: U-shaped recovery (left lip -> bottom ->
    right lip near the same level), followed by a shallow handle pullback,
    then a breakout above the cup's rim on rising volume.
    Returns (rim, cup_bottom) on a match, else None.
    """
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 40:
        return None

    closes = window["close"].values
    volumes = window["volume"].values

    third = len(closes) // 3
    left_idx = int(window["close"][:third].idxmax()) if third > 0 else 0
    left_peak = closes[left_idx]

    handle_start = len(closes) - handle_max_len
    if handle_start <= left_idx + 5:
        return None
    bottom_idx = left_idx + int(window["close"][left_idx:handle_start].idxmin() - left_idx)
    cup_bottom = closes[bottom_idx]

    cup_depth = _pct(cup_bottom, left_peak)
    if not (-0.50 <= cup_depth <= -0.12):
        return None

    if handle_start <= bottom_idx + 3:
        return None
    right_slice = window["close"][bottom_idx:handle_start]
    right_idx = int(right_slice.idxmax())
    right_peak = closes[right_idx]

    if not (0.80 <= (right_peak / left_peak) <= 1.20):
        return None

    handle_region = closes[right_idx + 1 :]
    if len(handle_region) < 3:
        return None
    handle_low = handle_region.min()
    handle_depth = _pct(handle_low, right_peak)
    if not (-0.15 <= handle_depth < 0):
        return None
    if abs(handle_depth) >= abs(cup_depth) * 0.75:
        return None

    rim = max(left_peak, right_peak)
    latest_close = closes[-1]
    avg_vol = volumes[-config.VOLUME_AVG_WINDOW:-1].mean() if len(volumes) > config.VOLUME_AVG_WINDOW else volumes[:-1].mean()
    if latest_close > rim and volumes[-1] > avg_vol:
        return float(rim), float(cup_bottom)
    return None


# ------------------------------------------------------------ Ascending Triangle
def detect_ascending_triangle(df, lookback=60, tolerance=0.03):
    """Returns (resistance_level, base_low) on a match, else None."""
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 20:
        return None

    highs_idx, lows_idx = find_pivots(window["close"], window=3)
    if len(highs_idx) < 2 or len(lows_idx) < 2:
        return None

    recent_highs = [window["close"][i] for i in highs_idx[-3:]]
    flat_resistance = (max(recent_highs) - min(recent_highs)) / max(recent_highs) <= tolerance

    recent_lows = [(i, window["close"][i]) for i in lows_idx[-3:]]
    rising_lows = all(recent_lows[i][1] < recent_lows[i + 1][1] for i in range(len(recent_lows) - 1))

    if not (flat_resistance and rising_lows):
        return None

    resistance_level = max(recent_highs)
    base_low = min(v for _, v in recent_lows)
    latest_close = window["close"].iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    if latest_close > resistance_level * (1 + tolerance / 2) and window["volume"].iloc[-1] > avg_vol:
        return float(resistance_level), float(base_low)
    return None


# ----------------------------------------------------------------------- Bull Flag
def detect_bull_flag(df, pole_window=10, flag_window=15, min_pole_gain=0.10):
    """Returns (breakout_level, pole_start_price) on a match, else None.
    pole_start_price is used for the measured move - classic technique is
    projecting the pole's own height above the breakout."""
    if len(df) < pole_window + flag_window + 2:
        return None

    pole = df.tail(pole_window + flag_window).head(pole_window)
    flag = df.tail(flag_window)

    pole_gain = _pct(pole["close"].iloc[-1], pole["close"].iloc[0])
    if pole_gain < min_pole_gain:
        return None

    flag_range = (flag["high"].max() - flag["low"].min()) / flag["close"].mean()
    if flag_range > 0.15:
        return None

    flag_drift = _pct(flag["close"].iloc[-1], flag["close"].iloc[0])
    if flag_drift > 0.05:
        return None

    flag_avg_vol = flag["volume"].iloc[:-1].mean()
    pole_avg_vol = pole["volume"].mean()
    if flag_avg_vol >= pole_avg_vol:
        return None

    breakout_level = flag["high"].iloc[:-1].max()
    latest = df.iloc[-1]
    if latest["close"] > breakout_level and latest["volume"] > flag_avg_vol:
        return float(breakout_level), float(pole["close"].iloc[0])
    return None


# ------------------------------------------------------------------- Double Bottom
def detect_double_bottom(df, lookback=90, tolerance=0.05, min_separation=10):
    """Returns (neckline, lower_of_the_two_bottoms) on a match, else None."""
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 30:
        return None

    _, lows_idx = find_pivots(window["close"], window=4)
    if len(lows_idx) < 2:
        return None

    idx1, idx2 = lows_idx[-2], lows_idx[-1]
    if idx2 - idx1 < min_separation:
        return None

    low1, low2 = window["close"][idx1], window["close"][idx2]
    if abs(_pct(low2, low1)) > tolerance:
        return None

    between = window["close"][idx1:idx2]
    if between.empty:
        return None
    neckline = between.max()

    latest_close = window["close"].iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    if latest_close > neckline and window["volume"].iloc[-1] > avg_vol:
        return float(neckline), float(min(low1, low2))
    return None


# ----------------------------------------------------------- Inverse Head & Shoulders
def detect_inverse_head_shoulders(df, lookback=90, shoulder_tolerance=0.08):
    """Returns (neckline, head_price) on a match, else None."""
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 30:
        return None

    _, lows_idx = find_pivots(window["close"], window=4)
    if len(lows_idx) < 3:
        return None

    left_i, head_i, right_i = lows_idx[-3], lows_idx[-2], lows_idx[-1]
    left, head, right = window["close"][left_i], window["close"][head_i], window["close"][right_i]

    if not (head < left and head < right):
        return None
    if abs(_pct(right, left)) > shoulder_tolerance:
        return None

    neckline = max(window["close"][left_i:head_i].max(), window["close"][head_i:right_i].max())
    latest_close = window["close"].iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    if latest_close > neckline and window["volume"].iloc[-1] > avg_vol:
        return float(neckline), float(head)
    return None


# ------------------------------------------------------- VCP (Volatility Contraction)
def detect_vcp(df, lookback=100, min_contractions=2):
    """
    Mark Minervini's Volatility Contraction Pattern: a series of pullbacks
    from swing highs, each shallower (and typically lower-volume) than the
    last, followed by a breakout above the most recent swing high on
    expanding volume. Returns (pivot_high, lowest_contraction_low).
    """
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 40:
        return None

    highs_idx, lows_idx = find_pivots(window["close"], window=4)
    if len(highs_idx) < min_contractions or len(lows_idx) < min_contractions:
        return None

    pivots = sorted(highs_idx + lows_idx)
    depths = []
    for i in range(len(pivots) - 1):
        a, b = pivots[i], pivots[i + 1]
        pa, pb = window["close"][a], window["close"][b]
        if pb < pa:
            depths.append(abs(_pct(pb, pa)))

    depths = depths[-min_contractions - 1:] if len(depths) >= min_contractions else depths
    if len(depths) < min_contractions:
        return None

    contracting = all(depths[i] > depths[i + 1] for i in range(len(depths) - 1))
    if not contracting:
        return None

    pivot_high = window["close"][highs_idx[-1]]
    contraction_low = min(window["close"][i] for i in lows_idx[-min_contractions:])
    latest = window.iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    if latest["close"] > pivot_high and latest["volume"] > avg_vol:
        return float(pivot_high), float(contraction_low)
    return None


DETECTORS = {
    "Cup and Handle": detect_cup_and_handle,
    "Ascending Triangle": detect_ascending_triangle,
    "Bull Flag": detect_bull_flag,
    "Double Bottom": detect_double_bottom,
    "Inverse Head and Shoulders": detect_inverse_head_shoulders,
    "VCP Breakout": detect_vcp,
}


def detect_chart_patterns(df):
    """
    Returns a list of (pattern_name, breakout_level, pattern_low) tuples for
    every enabled pattern that matched (usually 0 or 1 entries).
    """
    matches = []
    for name, fn in DETECTORS.items():
        if name not in config.ENABLED_CHART_PATTERNS:
            continue
        try:
            result = fn(df)
        except Exception:
            continue
        if result is not None:
            level, pattern_low = result
            matches.append((name, level, pattern_low))
    return matches
