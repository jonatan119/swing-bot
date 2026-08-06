"""
Translates the stop-loss distance already computed by the strategy into an
actual number of shares to buy, given how much of your account you want to
risk per trade. This is what turns "here's a setup" into "here's exactly
what to do about it."
"""
import math
import config


def compute_position_size(entry_price, stop_loss):
    """
    Returns a dict: dollar_risk, shares, position_value, position_pct_of_equity.
    Uses config.ACCOUNT_EQUITY and config.RISK_PER_TRADE_PCT - edit those in
    config.py to match your actual account size and risk tolerance.
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
