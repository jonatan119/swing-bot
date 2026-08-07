"""
Turns a match into a 0-100 conviction score instead of a flat pass/fail.
Every alert already had to clear every hard gate (trend, MACD, pattern,
volume, RS, earnings) - this score ranks *how strongly* it cleared them,
so you can tell a barely-qualifying setup from an exceptional one at a
glance, and optionally filter out the weak end entirely
(config.MIN_SIGNAL_SCORE).

All weights and scaling live in config.py - tune them there.
"""
import config


def _clamp(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, value))


def compute_score(*, price, ema50, macd, macd_signal, volume_ratio, rs_outperformance, num_patterns, rating):
    """Returns (score_0_to_100, breakdown_dict) for transparency in the alert."""

    # Trend strength: how far price is stretched above the 50 EMA.
    # 0% above = weak (score 0), 10%+ above = strong (score 100).
    trend_pct = (price - ema50) / ema50 * 100
    trend_score = _clamp(trend_pct / 10 * 100)

    # MACD strength: size of the bullish crossover relative to price.
    macd_gap_pct = (macd - macd_signal) / price * 100
    macd_score = _clamp(macd_gap_pct / 0.5 * 100)  # 0.5% gap -> full score

    # Volume: 120% of average = baseline pass, 200%+ = full score.
    volume_score = _clamp((volume_ratio - 1.0) / (2.0 - 1.0) * 100)

    # Relative strength vs SPY: 0% outperformance = weak, 20%+ = full score.
    rs_score = _clamp(rs_outperformance / 20 * 100)

    # Confirmation bonus: more independent patterns agreeing = more conviction.
    pattern_score = _clamp(num_patterns * 40)  # 1 pattern=40, 2=80, 3+=100

    # Analyst rating: a SCORING factor, not a hard gate (see config.py) -
    # strong ratings boost conviction, weak/unavailable ratings don't block
    # the setup outright, they just don't get full credit here.
    analyst_score = config.ANALYST_RATING_SCORES.get(rating, config.ANALYST_RATING_SCORE_IF_UNKNOWN)

    weights = config.SCORE_WEIGHTS
    score = (
        trend_score * weights["trend"]
        + macd_score * weights["macd"]
        + volume_score * weights["volume"]
        + rs_score * weights["relative_strength"]
        + pattern_score * weights["pattern_confirmation"]
        + analyst_score * weights["analyst_rating"]
    )

    breakdown = {
        "trend_score": round(trend_score, 1),
        "macd_score": round(macd_score, 1),
        "volume_score": round(volume_score, 1),
        "rs_score": round(rs_score, 1),
        "pattern_score": round(pattern_score, 1),
        "analyst_score": round(analyst_score, 1),
    }
    return round(_clamp(score), 1), breakdown


def conviction_label(score):
    if score >= config.SCORE_HIGH_CONVICTION:
        return "🔥 High Conviction"
    if score >= config.SCORE_MEDIUM_CONVICTION:
        return "✅ Good Setup"
    return "👀 Watch"
