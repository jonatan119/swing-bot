"""
Owns the trade's risk/reward structure: dynamic stop-loss, dynamic take-
profit, the resulting R:R ratio, the R:R gatekeeper, and (optionally) share
sizing off that structure.

This replaces the old fixed 1:2 R:R model. Stop and target are now derived
from real technical structure (support/resistance) with an ATR-based
fallback only when no clear level exists - and any setup whose resulting
R:R doesn't clear MIN_RR_RATIO is rejected outright, not adjusted or forced
through.
"""
import math
import config


def compute_atr_stop_multiplier(atr_pct):
    """
    Returns the ATR multiplier to use for this specific stock's stop
    distance, sliding between config.ATR_MULTIPLIER_HIGH_VOL (for volatile
    stocks) and config.ATR_MULTIPLIER_LOW_VOL (for calm stocks) based on the
    stock's own ATR%. A fixed multiplier doesn't adapt: a high-ATR stock at
    1.5x can produce an oversized stop even after other adjustments, while a
    low-ATR stock can afford more room (in multiple terms) since its ATR is
    already small in absolute terms. Linearly interpolated between the two
    volatility thresholds; clamped at the edges.
    """
    low_thresh = config.ATR_LOW_VOL_THRESHOLD_PCT
    high_thresh = config.ATR_HIGH_VOL_THRESHOLD_PCT

    if atr_pct <= low_thresh:
        return config.ATR_MULTIPLIER_LOW_VOL
    if atr_pct >= high_thresh:
        return config.ATR_MULTIPLIER_HIGH_VOL

    # Linear interpolation between the two thresholds.
    span = high_thresh - low_thresh
    position = (atr_pct - low_thresh) / span  # 0 at low_thresh, 1 at high_thresh
    return config.ATR_MULTIPLIER_LOW_VOL + position * (config.ATR_MULTIPLIER_HIGH_VOL - config.ATR_MULTIPLIER_LOW_VOL)


def compute_dynamic_trade_plan(entry_price, atr_value, support_level, resistance_level, measured_move_target=None):
    """
    Returns a trade-plan dict, or None if the setup fails the R:R gatekeeper
    (config.MIN_RR_RATIO) - callers should treat None as "reject this setup,
    do not alert."

    Stop-loss:
      - If a support level below entry exists, stop = support * (1 - buffer%).
      - Otherwise falls back to entry - dynamic_atr_multiplier * ATR, where
        the multiplier itself SLIDES between 1.0x-1.5x based on how volatile
        this specific stock is (see compute_atr_stop_multiplier).
      - Whichever of those is tighter than the MAX_STOP_LOSS_PCT % cap wins
        (i.e. the cap can only tighten the stop, never widen it).

    Take-profit (priority order):
      1. Next real swing resistance above entry, if one exists - the most
         grounded target (an actual level the market has respected before).
      2. Measured-move projection (pattern height added above the breakout)
         if a chart pattern fired - a real technique, not a guess, and often
         more realistic than "no resistance found so just use flat ATR."
      3. ATR-based projection (TARGET_ATR_MULTIPLIER) as the last resort.
    """
    atr_pct = atr_value / entry_price * 100
    atr_multiplier = compute_atr_stop_multiplier(atr_pct)

    # ---- Stop-loss: structure-based first, ATR as fallback ----
    stop_basis = "ATR"
    if support_level is not None and support_level < entry_price:
        structure_stop = support_level * (1 - config.STOP_BUFFER_BELOW_SUPPORT_PCT / 100)
        stop_basis = "Support"
    else:
        structure_stop = entry_price - atr_multiplier * atr_value

    # ---- Floor: never let the stop sit tighter than normal daily noise. A
    # support level can happen to sit very close to entry (e.g. right at a
    # just-broken resistance level) - without this floor, the stop would be
    # tighter than the stock's own ATR, guaranteeing a fast, meaningless
    # stop-out regardless of whether the trade thesis was right. Uses the
    # same sliding multiplier - a volatile stock's floor is tighter (1.0x)
    # than a calm stock's floor (up to 1.5x). ----
    min_distance_floor = atr_multiplier * atr_value
    if (entry_price - structure_stop) < min_distance_floor:
        structure_stop = entry_price - min_distance_floor
        stop_basis = f"{stop_basis} (ATR floor)"

    pct_cap_stop = entry_price * (1 - config.MAX_STOP_LOSS_PCT / 100)
    if pct_cap_stop > structure_stop:
        # The % cap wants a tighter stop than the ATR noise floor allows -
        # this stock is simply too volatile for the configured risk budget.
        # Forcing the tighter stop through would recreate the exact bug this
        # floor exists to prevent, so reject the setup instead.
        return None
    stop_loss = structure_stop

    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        return None  # degenerate case - stop above/at entry, can't size this trade

    # ---- Take-profit: resistance -> measured move -> ATR, in that order ----
    if resistance_level is not None and resistance_level > entry_price:
        take_profit = resistance_level
        target_basis = "Resistance"
    elif measured_move_target is not None and measured_move_target > entry_price:
        take_profit = measured_move_target
        target_basis = "Measured Move"
    else:
        take_profit = entry_price + config.TARGET_ATR_MULTIPLIER * atr_value
        target_basis = "ATR"

    reward_per_share = take_profit - entry_price
    if reward_per_share <= 0:
        return None

    rr_ratio = reward_per_share / risk_per_share

    # ---- Gatekeeper: reject outright if the real R:R doesn't clear the bar ----
    if rr_ratio < config.MIN_RR_RATIO:
        return None

    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "stop_pct": (stop_loss - entry_price) / entry_price * 100,
        "target_pct": (take_profit - entry_price) / entry_price * 100,
        "atr_pct": atr_pct,
        "atr_multiplier_used": round(atr_multiplier, 2),
        "rr_ratio": rr_ratio,
        "stop_basis": stop_basis,     # "Support", "ATR", or "% cap"
        "target_basis": target_basis,  # "Resistance" or "ATR"
    }


def compute_position_size(entry_price, stop_loss):
    """
    Returns a dict: dollar_risk, shares, position_value, position_pct_of_equity.
    Uses config.ACCOUNT_EQUITY and config.RISK_PER_TRADE_PCT - edit those in
    config.py to match your actual account size and risk tolerance. Off by
    default (config.ENABLE_POSITION_SIZING).
    """
    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        return None

    dollar_risk = config.ACCOUNT_EQUITY * (config.RISK_PER_TRADE_PCT / 100)
    shares = math.floor(dollar_risk / risk_per_share)
    position_value = shares * entry_price
    position_pct_of_equity = (position_value / config.ACCOUNT_EQUITY) * 100 if config.ACCOUNT_EQUITY else 0

    return {
        "dollar_risk": dollar_risk,
        "shares": shares,
        "position_value": position_value,
        "position_pct_of_equity": position_pct_of_equity,
    }
