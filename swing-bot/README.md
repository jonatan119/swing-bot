# Swing Trade Alert Bot

Scans the US stock market twice a day (market open + close) against your
strategy rules, and posts matches straight to a Discord channel via webhook.
Runs entirely in the cloud on GitHub Actions — no server, no laptop required.

## Strategy implemented

1. **Gatekeepers**: price > $5, market cap > $2B, avg daily volume > 500k,
   analyst consensus = Buy or Strong Buy.
2. **Trend**: price > 50 EMA > 150 SMA > 200 SMA.
3. **Trigger**: MACD bullish crossover (fires only on the crossover bar) +
   a price-action confirmation — either a bullish candlestick pattern
   (engulfing or hammer) OR a chart-pattern breakout:
   - Cup and Handle
   - Ascending Triangle
   - Bull Flag
   - Double Bottom
   - Inverse Head and Shoulders
   - VCP (Volatility Contraction Pattern — Minervini-style)

   Toggle which chart patterns are active in `config.py` →
   `ENABLED_CHART_PATTERNS`.
4. **Volume confirmation**: day's volume ≥ 120% of the 20-day average.
5. **Entry, stop-loss & take-profit**: entry = signal-day close; stop-loss =
   entry − 1.5×ATR(14); take-profit set for a 1:2 reward-to-risk ratio. Every
   alert shows the full trade plan (entry/stop/target/risk-per-share).
6. **Market regime filter**: no alerts fire while the S&P 500 (SPY) is below
   its own 200-day SMA. The exact same technical setup performs meaningfully
   worse in a broad downtrend — this is the single biggest false-positive
   reducer in the whole bot.
7. **Relative Strength (RS) vs SPY**: the stock's 6-month return must beat
   SPY's over the same period. A breakout in a market laggard is a much
   weaker signal than the same breakout in a leader.
8. **Earnings-date awareness**: alerts are suppressed if the stock reports
   earnings within `EARNINGS_BLACKOUT_DAYS` (default 5) — a gap can blow
   straight through an ATR-based stop regardless of setup quality.
9. **Signal scoring (0-100)**: every setup gets a composite conviction score
   from trend strength, MACD gap size, volume surge, RS outperformance, and
   number of confirming patterns. Anything below `MIN_SIGNAL_SCORE` (default
   60) is suppressed — this filters out setups that technically pass every
   rule but only barely.
10. **Position sizing** *(off by default)*: given `ACCOUNT_EQUITY` and
    `RISK_PER_TRADE_PCT` in `config.py`, alerts can tell you exactly how many
    shares to buy so you risk the same dollar amount every trade. Turn it on
    by setting `ENABLE_POSITION_SIZING = True` in `config.py`.

All analysis runs on the **daily (1D) timeframe** — this is fixed in
`config.TIMEFRAME`, not an intraday scanner.

Every rule, weight, and threshold lives in `config.py` — change numbers
there, no need to touch the scanning logic.

## Alert deduplication (no repeat alerts)

Once a symbol triggers an alert, it won't alert again for
`config.ALERT_COOLDOWN_DAYS` (default 14 days) even if you re-run the
scan or it still matches. This state is stored in `state/alerted_symbols.json`
and the GitHub Actions workflow automatically commits the updated file back
to your repo after each run (you'll see occasional "swing-bot" commits in
your repo history — that's expected and how the cooldown persists across runs).

## Chart image preview (TradingView via chart-img.com)

Each alert can include a snapshot image of the actual TradingView chart
(daily timeframe, with the 50/150/200 MA overlay) using
[chart-img.com](https://chart-img.com) — a service built specifically to
render TradingView charts as a hosted image via API (TradingView itself
doesn't offer this directly). This is optional: if you don't set up a key,
alerts are sent without the image and everything else still works.

## 1. Get an FMP API key

1. Sign up at https://financialmodelingprep.com
2. Free tier works for testing with a handful of tickers. For scanning the
   **full** US market twice a day you'll want a paid plan (roughly $15–30/mo)
   for higher rate limits — the free tier will throttle mid-scan.
3. Copy your API key.

## 2. Create a Discord webhook

1. In your Discord server: Server Settings → Integrations → Webhooks → New Webhook.
2. Pick the channel, copy the Webhook URL.

## 3. (Optional) Get a chart-img.com API key

Only needed if you want the TradingView chart preview image in each alert.

1. Sign up at https://chart-img.com (Google sign-in)
2. Generate a personal API key from your dashboard — a free tier is available.
3. Skip this step entirely if you don't want chart images; the bot works fine without it.

## 4. Push this project to a GitHub repo

```bash
cd swing-bot
git init
git add .
git commit -m "Swing trade alert bot"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 5. Add your secrets to the repo

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `FMP_API_KEY` | your Financial Modeling Prep key |
| `DISCORD_WEBHOOK_URL` | your Discord webhook URL |
| `CHART_IMG_API_KEY` | your chart-img.com key (optional — omit to skip chart images) |

## 6. That's it — fully automatic, no manual triggering needed

The workflow in `.github/workflows/scan.yml` runs **automatically** on
GitHub's servers via the `schedule` trigger — you never need to open GitHub
or click anything for normal operation:

- **Morning scan**: fires at market open (9:30am ET), output lands over midday.
- **Pre-close scan**: since a full scan takes ~2.5 hours, this one *starts*
  ~3 hours before market close (1:00pm ET) so the results land right around
  the closing bell instead of hours after the market's already shut.

(You'll actually see 4 cron entries in the workflow file — an EDT and EST
version of each run, since GitHub Actions cron doesn't shift for daylight
saving. Two of the four will fire at the "wrong" real-world time each half
of the year — harmless, just an extra scan, and the 14-day alert cooldown
means you won't get spammed with duplicates.)

The **"Run workflow"** button under the Actions tab is only for manual test
runs — it's not required for the bot to work day-to-day.

## Running locally (optional, for testing)

```bash
pip install -r requirements.txt
export FMP_API_KEY=your_key_here
export DISCORD_WEBHOOK_URL=your_webhook_here
python scanner.py
```

## Files

| File | Purpose |
|---|---|
| `config.py` | All strategy thresholds and API keys |
| `data_provider.py` | FMP API calls: screener, analyst rating, historical prices |
| `indicators.py` | EMA/SMA/MACD/ATR/volume calculations |
| `patterns.py` | Bullish engulfing / hammer candlestick detection |
| `chart_patterns.py` | Multi-bar chart patterns: cup & handle, triangles, flags, double bottom, inverse H&S, VCP |
| `chart_image.py` | Fetches a TradingView chart snapshot via chart-img.com |
| `state_store.py` | Alert cooldown / dedup state (reads & writes `state/alerted_symbols.json`) |
| `market_context.py` | Market regime (SPY vs 200 SMA) + relative strength calculations |
| `scoring.py` | Composite 0-100 conviction score |
| `position_sizing.py` | Converts stop distance + account risk % into a share count |
| `scanner.py` | Main pipeline — run this |
| `discord_alert.py` | Formats and sends Discord messages |
| `.github/workflows/scan.yml` | Cloud scheduler (GitHub Actions) |

## Notes & caveats

- **Not financial advice.** This is a mechanical filter, not a guarantee —
  always confirm signals yourself before trading.
- Analyst rating classification comes from FMP's aggregated data and can lag
  or vary between providers.
- Candlestick pattern detection here is a simplified rule-based version, not
  a full TA-Lib pattern library — it covers bullish engulfing and hammer only,
  matching what you specified.
- Chart patterns (cup & handle, triangles, flags, double bottom, inverse H&S,
  VCP) are detected with geometric heuristics on swing highs/lows, not a
  licensed pattern-recognition engine. They're a solid approximation of the
  textbook shapes but won't be pixel-perfect on every name — treat matches as
  candidates to review, same as the rest of the signals.
- GitHub Actions cron doesn't shift for daylight saving automatically, so the
  workflow includes both EST and EDT trigger times to stay close to real
  market open/close year-round.
- If FMP's free tier rate-limits mid-scan, some tickers will just be skipped
  (logged as errors) rather than crashing the whole run.
- Scanning 3,000+ tickers sequentially (as this bot does, with a polite delay
  between calls) takes roughly 1.5–2.5 hours per run on a free/low-tier FMP
  plan. It'll finish well within GitHub Actions' 6-hour limit, but if you
  want it faster, concurrent requests are the next upgrade (ask if you'd
  like that added — it needs to match your FMP plan's rate limit).
- The chart image is a snapshot at scan time, not a live/interactive chart —
  click through to TradingView yourself for real-time detail.
- **Set `ACCOUNT_EQUITY` in `config.py` to your real account size** before
  relying on the position-sizing numbers — it defaults to $10,000 as a
  placeholder.
- The market regime filter means some runs will send **zero** alerts by
  design (a single Discord notice explains why) — that's the bot correctly
  refusing to fight the broader trend, not a bug.
- RS and market-regime checks both depend on fetching SPY's own history each
  run — if that fetch fails (rare, but possible on a rate-limited plan), the
  bot logs a warning and skips those two checks for that run rather than
  crashing entirely.
