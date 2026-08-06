"""
Market-context checks that separate a "regular" scanner from one that
understands whether conditions actually favor the setups it's finding.

Two pieces:
  1. Market regime - is the S&P 500 itself in an uptrend? Minervini/O'Neil-
     style systems stop taking new longs when the index is below its own
     200-day SMA, because the same technical setup has a meaningfully worse
     win rate in a broad downtrend, no matter how clean it looks.
  2. Relative Strength (RS) - is this stock actually outperforming the
     index over the medium term? A breakout in a laggard is a much weaker
     signal than the same breakout in a market leader.
"""
import indicators as ind
import config


def compute_market_regime(spy_df):
    """
    Returns (is_healthy: bool, pct_vs_200sma: float, spy_close: float, spy_sma200: float).
    is_healthy = SPY's close is above its own 200-day SMA.
    """
    df = ind.add_all_indicators(spy_df)
    row = df.iloc[-1]
    close = float(row["close"])
    sma200 = float(row["sma200"])
    pct_vs_200sma = (close - sma200) / sma200 * 100
    return close > sma200, pct_vs_200sma, close, sma200


def compute_relative_strength(stock_df, spy_df, lookback_days=None):
    """
    Returns (rs_outperformance_pct, stock_return_pct, spy_return_pct).
    rs_outperformance_pct = stock's return minus SPY's return over the same
    lookback window - positive means the stock is beating the market.
    """
    lookback_days = lookback_days or config.RS_LOOKBACK_DAYS
    lookback_days = min(lookback_days, len(stock_df) - 1, len(spy_df) - 1)
    if lookback_days < 5:
        return 0.0, 0.0, 0.0

    stock_return = (
        stock_df["close"].iloc[-1] / stock_df["close"].iloc[-1 - lookback_days] - 1
    ) * 100
    spy_return = (
        spy_df["close"].iloc[-1] / spy_df["close"].iloc[-1 - lookback_days] - 1
    ) * 100

    return float(stock_return - spy_return), float(stock_return), float(spy_return)
