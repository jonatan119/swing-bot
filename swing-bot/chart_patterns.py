"""
Multi-bar chart pattern detection using swing-point (pivot) geometry.
These are heuristic, rule-based approximations of classic technical
patterns -- not a guarantee of the textbook shape, but tuned to catch
the setups swing traders consider high win-rate continuation/reversal
signals. No external TA library required.

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
    """
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 40:
        return False

    closes = window["close"].values
    volumes = window["volume"].values

    # Left lip: highest point in the first third of the window
    third = len(closes) // 3
    left_idx = int(window["close"][:third].idxmax()) if third > 0 else 0
    left_peak = closes[left_idx]

    # Cup bottom: lowest point after the left lip, excluding the final handle zone
    handle_start = len(closes) - handle_max_len
    if handle_start <= left_idx + 5:
        return False
    bottom_idx = left_idx + int(window["close"][left_idx:handle_start].idxmin() - left_idx)
    cup_bottom = closes[bottom_idx]

    cup_depth = _pct(cup_bottom, left_peak)
    if not (-0.50 <= cup_depth <= -0.12):   # cup should be a meaningful but not crash-like pullback
        return False

    # Right lip: highest point between cup bottom and start of handle zone, near left lip height
    if handle_start <= bottom_idx + 3:
        return False
    right_slice = window["close"][bottom_idx:handle_start]
    right_idx = int(right_slice.idxmax())
    right_peak = closes[right_idx]

    if not (0.85 <= (right_peak / left_peak) <= 1.15):
        return False  # rim should roughly line up on both sides

    # Handle: shallow pullback after the right lip, shallower than the cup itself
    handle_region = closes[right_idx + 1 :]
    if len(handle_region) < 3:
        return False
    handle_low = handle_region.min()
    handle_depth = _pct(handle_low, right_peak)
    if not (-0.15 <= handle_depth < 0):
        return False
    if abs(handle_depth) >= abs(cup_depth) * 0.6:
        return False  # handle must be materially shallower than the cup

    # Breakout: latest close above the cup rim, on above-average volume
    rim = max(left_peak, right_peak)
    latest_close = closes[-1]
    avg_vol = volumes[-config.VOLUME_AVG_WINDOW:-1].mean() if len(volumes) > config.VOLUME_AVG_WINDOW else volumes[:-1].mean()
    return latest_close > rim and volumes[-1] > avg_vol


# ------------------------------------------------------------ Ascending Triangle
def detect_ascending_triangle(df, lookback=60, tolerance=0.02):
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 20:
        return False

    highs_idx, lows_idx = find_pivots(window["close"], window=3)
    if len(highs_idx) < 2 or len(lows_idx) < 2:
        return False

    recent_highs = [window["close"][i] for i in highs_idx[-3:]]
    flat_resistance = (max(recent_highs) - min(recent_highs)) / max(recent_highs) <= tolerance

    recent_lows = [(i, window["close"][i]) for i in lows_idx[-3:]]
    rising_lows = all(recent_lows[i][1] < recent_lows[i + 1][1] for i in range(len(recent_lows) - 1))

    if not (flat_resistance and rising_lows):
        return False

    resistance_level = max(recent_highs)
    latest_close = window["close"].iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    return latest_close > resistance_level * (1 + tolerance / 2) and window["volume"].iloc[-1] > avg_vol


# ----------------------------------------------------------------------- Bull Flag
def detect_bull_flag(df, pole_window=10, flag_window=15, min_pole_gain=0.15):
    if len(df) < pole_window + flag_window + 2:
        return False

    pole = df.tail(pole_window + flag_window).head(pole_window)
    flag = df.tail(flag_window)

    pole_gain = _pct(pole["close"].iloc[-1], pole["close"].iloc[0])
    if pole_gain < min_pole_gain:
        return False  # need a sharp flagpole move up

    flag_range = (flag["high"].max() - flag["low"].min()) / flag["close"].mean()
    if flag_range > 0.15:
        return False  # flag should be a tight consolidation, not another big swing

    flag_drift = _pct(flag["close"].iloc[-1], flag["close"].iloc[0])
    if flag_drift > 0.05:
        return False  # flag should drift flat/down slightly, not keep ripping

    flag_avg_vol = flag["volume"].iloc[:-1].mean()
    pole_avg_vol = pole["volume"].mean()
    if flag_avg_vol >= pole_avg_vol:
        return False  # volume should dry up during the flag

    breakout_level = flag["high"].iloc[:-1].max()
    latest = df.iloc[-1]
    return latest["close"] > breakout_level and latest["volume"] > flag_avg_vol


# ------------------------------------------------------------------- Double Bottom
def detect_double_bottom(df, lookback=90, tolerance=0.03, min_separation=10):
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 30:
        return False

    _, lows_idx = find_pivots(window["close"], window=4)
    if len(lows_idx) < 2:
        return False

    # Compare the two most recent significant lows
    idx1, idx2 = lows_idx[-2], lows_idx[-1]
    if idx2 - idx1 < min_separation:
        return False

    low1, low2 = window["close"][idx1], window["close"][idx2]
    if abs(_pct(low2, low1)) > tolerance:
        return False  # lows should be roughly equal

    between = window["close"][idx1:idx2]
    if between.empty:
        return False
    neckline = between.max()

    latest_close = window["close"].iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    return latest_close > neckline and window["volume"].iloc[-1] > avg_vol


# ----------------------------------------------------------- Inverse Head & Shoulders
def detect_inverse_head_shoulders(df, lookback=90, shoulder_tolerance=0.06):
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 30:
        return False

    _, lows_idx = find_pivots(window["close"], window=4)
    if len(lows_idx) < 3:
        return False

    left_i, head_i, right_i = lows_idx[-3], lows_idx[-2], lows_idx[-1]
    left, head, right = window["close"][left_i], window["close"][head_i], window["close"][right_i]

    if not (head < left and head < right):
        return False  # head must be the deepest low
    if abs(_pct(right, left)) > shoulder_tolerance:
        return False  # shoulders roughly symmetric

    neckline = max(window["close"][left_i:head_i].max(), window["close"][head_i:right_i].max())
    latest_close = window["close"].iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    return latest_close > neckline and window["volume"].iloc[-1] > avg_vol


# ------------------------------------------------------- VCP (Volatility Contraction)
def detect_vcp(df, lookback=100, min_contractions=2):
    """
    Mark Minervini's Volatility Contraction Pattern: a series of pullbacks
    from swing highs, each shallower (and typically lower-volume) than the
    last, followed by a breakout above the most recent swing high on
    expanding volume.
    """
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 40:
        return False

    highs_idx, lows_idx = find_pivots(window["close"], window=4)
    if len(highs_idx) < min_contractions or len(lows_idx) < min_contractions:
        return False

    # Build contraction depths from consecutive high->low legs
    pivots = sorted(highs_idx + lows_idx)
    depths = []
    for i in range(len(pivots) - 1):
        a, b = pivots[i], pivots[i + 1]
        pa, pb = window["close"][a], window["close"][b]
        if pb < pa:  # a down-leg
            depths.append(abs(_pct(pb, pa)))

    depths = depths[-min_contractions - 1:] if len(depths) >= min_contractions else depths
    if len(depths) < min_contractions:
        return False

    contracting = all(depths[i] > depths[i + 1] for i in range(len(depths) - 1))
    if not contracting:
        return False

    pivot_high = window["close"][highs_idx[-1]]
    latest = window.iloc[-1]
    avg_vol = window["volume"].iloc[-config.VOLUME_AVG_WINDOW:-1].mean()
    return latest["close"] > pivot_high and latest["volume"] > avg_vol


DETECTORS = {
    "Cup and Handle": detect_cup_and_handle,
    "Ascending Triangle": detect_ascending_triangle,
    "Bull Flag": detect_bull_flag,
    "Double Bottom": detect_double_bottom,
    "Inverse Head and Shoulders": detect_inverse_head_shoulders,
    "VCP Breakout": detect_vcp,
}


def detect_chart_patterns(df):
    """Returns a list of matched chart-pattern names (usually 0 or 1)."""
    matches = []
    for name, fn in DETECTORS.items():
        if name not in config.ENABLED_CHART_PATTERNS:
            continue
        try:
            if fn(df):
                matches.append(name)
        except Exception:
            continue
    return matches
