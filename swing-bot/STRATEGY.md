# Swing Bot — Complete Current Strategy Reference

**Updated**: gates loosened per explicit request — trend alignment no
longer requires MA-to-MA stacking (4% tolerance), MACD is scoring-only (no
longer a hard gate), volume spike floor lowered to 85%, stop-loss cap raised
to 8%, anti-chasing band widened to -1.5%/+7.0%.

This is a full, accurate list of every rule, indicator, and threshold the bot
currently uses — pulled directly from the live code, not from memory. Given
how many parameters have changed over time, treat this as the source of
truth over anything said earlier in conversation.

Every gate below runs **in this exact order**, per ticker. The first one
that fails rejects the ticker immediately — later gates never even get
checked for a rejected ticker. This matters for understanding *why* the bot
is inconsistent: a stock can fail for very different reasons on different
days, and small threshold changes early in the sequence affect everything
downstream.

---

## Step 0 — Universe selection (before any per-ticker logic)

Pulled from FMP's `company-screener` endpoint in one API call:

| Filter | Value |
|---|---|
| Market cap | ≥ **$1.5B**, no ceiling |
| Price | ≥ **$5** |
| Exchange | NYSE, NASDAQ, AMEX |
| Country | US-domiciled only (excludes foreign ADRs) |
| Actively trading | Yes |
| ETFs / Funds | **Excluded** (isEtf=false, isFund=false, plus a defensive double-check on the response) |
| Volume (screener-level only) | ≥ 50,000 — deliberately loose; see note below |

**Why the volume filter is loose here:** the screener's volume field appears
to reflect *today's still-accumulating* intraday volume, not a stable daily
figure — so a scan running at market open sees far fewer qualifying stocks
than one running mid-afternoon, purely from timing. The **real** 500K/day
threshold is enforced later (Step 2) against stable end-of-day data instead.

This step alone determines your **scanned universe size** — typically
somewhere in the range of ~1,500–2,500 stocks, and this is the single
biggest lever if you want to scan "more" or "fewer" stocks. It is NOT
affected by anything below.

---

## Step 1 — Per-ticker hard gates (in order)

Every ticker from the universe goes through these checks, in this exact
sequence. **Any failure = instant rejection, no alert, gate order matters.**

1. **Sufficient history** — needs ≥205 daily bars (200 SMA + buffer). Rejects
   recent IPOs / thin data.
2. **Current-day volume ≥ 500,000 shares** (stable EOD data, not the
   screener's live figure).
3. **20-day average volume ≥ 500,000 shares.**
4. **Trend alignment (loosened)**: `Price > 50 EMA`, `Price > 150 SMA`, and
   `Price > 200 SMA`, checked **independently** — the moving averages no
   longer need to be perfectly stacked (50 EMA > 150 SMA > 200 SMA) among
   themselves. Tolerance widened to **4%**.
5. **MACD momentum — no longer a hard gate.** MACD is now purely a
   **scoring** factor (see Step 5) — a bullish MACD earns more points, a
   bearish/flat one earns fewer, but nothing gets rejected outright over it.
6. **Price-action trigger** — at least ONE of the following must be present
   (see "Pattern Detection" section below for full detail on each):
   - A bullish candlestick pattern (Engulfing or Hammer), OR
   - A chart-pattern breakout (Cup & Handle, Ascending Triangle, Bull Flag,
     Double Bottom, Inverse Head & Shoulders, VCP), OR
   - A POC Volume Test (price holding at the heaviest-traded price level
     with elevated volume), OR
   - An Uptrend Trendline Bounce (price holding a genuine multi-touch
     ascending trendline, with volume)
7. **Volume spike (loosened)**: today's volume ≥ **85%** of the 20-day
   average — no longer requires an actual spike above average, just
   reasonably close to it (accounts for intraday scans catching a
   still-accumulating volume day).
8. **Anti-chasing gate (widened)**: today's price change (close vs.
   yesterday's close) must fall between **-1.5% and +7.0%** — now allows
   slight pullback/red days through, not just up days.
9. **Relative Strength vs. SPY**: the stock's 6-month return must not lag
   SPY's by more than **3 percentage points** (i.e. it can't be a real
   laggard, but doesn't have to be beating the market either).
10. **Earnings blackout**: rejected if the company reports earnings within
    the next **5 days** (gap risk).
11. **Entry freshness (live price check)**: fetches a real-time quote and
    compares it to the calculated entry:
    - Rejected outright if live price is **more than 4% above** the
      calculated entry (opportunity already gone).
    - Rejected outright if live price is **more than 2% below** the
      calculated entry (thesis may already be broken / entry is stale in
      the other direction).
    - If live price is 1–4% above a "Resistance Breakout" entry
      specifically, the alert is **relabeled** "Support Retest (former
      resistance)" instead of rejected — the breakout already happened, so
      it's presented as a pullback-entry opportunity instead.
12. **Dynamic Risk:Reward gatekeeper**: stop-loss and take-profit are
    calculated from real structure (see "Risk Management" below); if the
    resulting R:R comes out below **1:1.5**, the setup is **rejected
    entirely** — no fallback, no exception.
13. **Minimum score**: the composite 0–100 score (see "Scoring" below) must
    be at least **30** or the setup is rejected even as a backfill
    candidate.

---

## Step 2 — Pattern detection (Step 1's gate #6, in detail)

All chart patterns require **genuine structural depth** — a minimum 5–8%
range/depth requirement was added specifically because early versions
falsely matched ordinary uptrend noise as "patterns."

| Pattern | Core requirement | Min depth/range enforced |
|---|---|---|
| **Cup and Handle** | U-shaped recovery + shallower handle pullback + breakout above rim on volume | Cup depth 12–50%, handle < 60–75% of cup depth |
| **Ascending Triangle** | Flat resistance (3 touches within 3%) + rising lows + breakout | Base range ≥ 8% |
| **Bull Flag** | Sharp pole move (≥10%) + tight low-volume consolidation + breakout | — |
| **Double Bottom** | Two similar lows + neckline breakout | Neckline ≥ 5% above both lows (prevents false positives from ordinary pullback noise) |
| **Inverse Head & Shoulders** | Three troughs (middle deepest) + neckline breakout | Head ≥ 5% below neckline |
| **VCP Breakout** | Contracting pullback sequence + breakout on expanding volume | First (largest) contraction ≥ 8% |
| **POC Volume Test** | Price within 3% of the volume-profile Point of Control + volume ≥110% of average | — |
| **Uptrend Trendline Bounce** | Least-squares line fit through 3 recent swing lows, positive slope, lows within 3% of the fitted line, price currently holding above it + volume confirmation | — |

Any candlestick pattern (Engulfing, Hammer) OR any one chart pattern OR
either of the two "standalone" triggers (POC test, trendline bounce) is
sufficient to pass gate #6 — they are not required together.

---

## Step 3 — Entry price logic

Entry is **never** just "today's closing price" — it's derived from actual
structure, checked in this priority order:

1. **Resistance Breakout** — if a chart pattern fired, entry = that
   pattern's own breakout level (rim/resistance/neckline) + 0.3% buffer. The
   broken level becomes the new support reference.
2. **Uptrend Trendline Bounce** — entry = current price, support reference =
   the fitted trendline's value.
3. **POC Support Hold** — entry = current price, support reference = the
   Point of Control, if price is within 3% above it.
4. **Support Bounce** — entry = current price, support reference = nearest
   prior swing low, if within 3% above it.
5. **Unconfirmed** — fallback to current price with no clean structural
   reference, clearly labeled as such.

(Then Step 1 gate #11 may override the label to "Support Retest" if live
price has already moved past a Resistance Breakout entry.)

---

## Step 4 — Risk management (dynamic, not fixed 1:2)

**Stop-loss** (whichever is tighter wins):
- If a support level exists: `support × (1 − 0.5%)` (small buffer below it)
- Otherwise: `entry − (sliding ATR multiplier) × ATR`
- **The ATR multiplier slides between 1.0x–1.5x** based on the stock's own
  ATR%: calm stocks (ATR% ≤ 2%) get the full 1.5x; volatile stocks (ATR% ≥
  5%) get tightened to 1.0x; linear interpolation in between.
- A hard cap of **8% max stop distance** applies regardless — if even the
  ATR-based floor would exceed 5%, the setup is rejected (too volatile for
  the risk budget) rather than forcing an unsafe compromise.

**Take-profit** (first available wins):
1. Next real swing resistance level above entry, if one exists
2. **Measured-move projection** — the matched pattern's own height (rim −
   base) projected upward from the breakout point (e.g. cup depth, flag
   pole height, head-and-shoulders depth) — a real technique, not a guess
3. ATR-based projection (3x ATR) as the last resort

**R:R gatekeeper**: computed from the above real numbers; must be ≥1:1.5 or
the setup is rejected (Step 1, gate #12).

---

## Step 5 — Composite scoring (0–100)

Every setup that clears all hard gates gets scored on 6 weighted factors:

| Factor | Weight | What it measures |
|---|---|---|
| Trend strength | 20% | How far price is stretched above the 50 EMA |
| MACD strength | 15% | Size of the bullish crossover gap |
| Volume | 15% | Volume ratio vs. 20-day average |
| Relative Strength | 20% | Outperformance vs. SPY over 6 months |
| Pattern confirmation | 15% | Number of independent patterns agreeing |
| Analyst rating | 15% | Strong Buy=100, Buy=75, Hold=40, Sell=10, Strong Sell=0, no coverage=30 |

**Note**: analyst rating is a *scoring* factor now, not a hard gate — it was
originally a hard pass/fail requirement, but that alone rejected 44% of all
scanned tickers in one measured run, so it was converted to a weighted
factor per the "prioritize OR filter" language in the original spec.

- Score ≥60 → alerts normally, labeled "✅ Good Setup"
- Score ≥80 → labeled "🔥 High Conviction"
- Score <60 but ≥30 → only alerts as a **backfill** (see below)
- Score <30 → rejected outright, never alerts

---

## Step 6 — Ranking and guaranteed minimum results

After all tickers are evaluated:
1. Anything still within its **14-day cooldown** (already alerted recently)
   is excluded.
2. Remaining candidates are ranked by score, highest first.
3. Everything scoring ≥60 always alerts.
4. If fewer than **15** total alerts would go out, the bot backfills with
   the next-highest scorers (down to the score-30 floor) until either 15 is
   reached or candidates run out.

This means on a strong day you might get 15+ high-quality alerts; on a weak
day you might get anywhere from 0 (if very few real setups exist, or if the
market regime check below blocks everything) up to 15 lower-scored ones.

---

## Step 7 — Market regime override (checked once, before any tickers)

Before scanning individual stocks, the bot checks SPY against its own
200-day SMA:
- **If SPY is below its 200-day SMA, the bot sends ZERO alerts for that
  entire run**, regardless of how good any individual setup looks. A single
  Discord notice explains why. This is deliberate — the same technical
  setup has a meaningfully worse real-world win rate in a broad market
  downtrend.

---

## Why results feel inconsistent — the honest explanation

With **13 sequential hard gates**, a scoring system, a ranking/backfill
system, and a market-wide override, small day-to-day differences compound:
- A quiet market day can legitimately produce far fewer (or zero) qualifying
  setups than an active one — this isn't a bug, it's 13 independent
  conditions all needing to align.
- The universe size itself varies day to day based on which stocks currently
  clear the $1.5B/price/volume bar.
- The market regime check can zero out an entire day by itself.
- Live-price staleness checks reject setups where the EOD-based signal has
  already gone stale by the time the scan reaches you.

If you want to see **exactly** why a specific run produced what it did, the
GitHub Actions log for that run prints a full rejection breakdown (how many
tickers failed at each specific gate) — that's the most reliable way to
diagnose a specific day's results rather than guessing from the Discord
summary alone.
