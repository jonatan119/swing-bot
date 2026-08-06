# Swing Trade Alert Bot

Scans the US stock market twice a day (market open + close) against your
strategy rules, and posts matches straight to a Discord channel via webhook.
Runs entirely in the cloud on GitHub Actions — no server, no laptop required.

## Strategy implemented

1. **Gatekeepers**: price > $5, market cap > $2B, avg daily volume > 500k,
   analyst consensus = Buy or Strong Buy.
2. **Trend**: price > 50 EMA > 150 SMA > 200 SMA.
3. **Trigger**: MACD bullish crossover within the last `MACD_CROSSOVER_LOOKBACK_DAYS`
   (default 3 sessions, still currently above the signal line) + a price-action
   confirmation — either a bullish candlestick pattern (engulfing or hammer)
   OR a chart-pattern breakout:
   - Cup and Handle
   - Ascending Triangle
   - Bull Flag
   - Double Bottom
   - Inverse Head and Shoulders
   - VCP (Volatility Contraction Pattern — Minervini-style)

   Toggle which chart patterns are active in `config.py` →
   `ENABLED_CHART_PATTERNS`.
4. **Volume confirmation**: day's volume ≥ 120% of the 20-day average.
5. **Strategic entry** (not just today's close): entry is derived from actual
   technical structure, in priority order:
   - **Resistance Breakout** — if a chart pattern fired, entry = that
     pattern's own breakout level (cup rim, triangle resistance, flag high,
     neckline, etc.) + a small buffer, i.e. you're entering on confirmed
     strength above real resistance, not at an arbitrary closing price.
   - **POC Support Hold** — if no breakout pattern fired but price is
     holding near the volume-profile Point of Control (the price level with
     the heaviest traded volume recently — a real support/resistance
     reference), entry = current price.
   - **Support Bounce** — same idea, using the nearest prior swing low.
   - **Unconfirmed** — fallback to current price if none of the above apply,
     clearly labeled as such in the alert so it's never silently assumed.
6. **Risk management (capped ATR stop)**: stop-loss = whichever is *tighter*
   of (a) entry − 1.5×ATR(14), or (b) a hard `MAX_STOP_LOSS_PCT` cap (default
   5%). This fixes the problem where a highly volatile stock (e.g. 6% daily
   ATR) would otherwise get a stop nearly twice as wide as a calmer one —
   volatile names get capped, calm names still get their natural (often
   tighter) ATR-based stop. Take-profit is set for a 1:2 reward-to-risk ratio
   off the actual (capped) risk. ATR is shown in both dollars and % of price.
7. **Market regime filter**: no alerts fire while the S&P 500 (SPY) is below
   its own 200-day SMA. The exact same technical setup performs meaningfully
   worse in a broad downtrend — this is the single biggest false-positive
   reducer in the whole bot.
8. **Relative Strength (RS) vs SPY**: the stock's 6-month return must beat
   SPY's over the same period. A breakout in a market laggard is a much
   weaker signal than the same breakout in a leader.
9. **Earnings-date awareness**: alerts are suppressed if the stock reports
   earnings within `EARNINGS_BLACKOUT_DAYS` (default 5) — a gap can blow
   straight through an ATR-based stop regardless of setup quality.
10. **Signal scoring (0-100) + guaranteed minimum results**: every setup that
    clears the hard gates gets a composite conviction score from trend
    strength, MACD gap size, volume surge, RS outperformance, and number of
    confirming patterns. Rather than only alerting whatever happens to clear
    `MIN_SIGNAL_SCORE` (default 60) — which on a quiet day could be 0, 1, or
    2 stocks — the bot ranks *every* candidate across the whole universe and
    backfills down to `ABSOLUTE_MIN_SCORE` (default 40) as needed to send at
    least `MIN_RESULTS_PER_SCAN` (default 5) alerts whenever the universe
    contains that many qualifying candidates.
11. **Position sizing** *(off by default)*: given `ACCOUNT_EQUITY` and
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

## Troubleshooting: "I keep seeing the same stocks every scan"

This has two possible causes — check both:

1. **The cooldown state isn't actually being saved.** The bot writes
   `state/alerted_symbols.json` and the workflow commits it back to your repo
   after every run. If that commit/push step is failing silently, every run
   starts from an empty cooldown and the same top candidates repeat forever.
   **Go check:** your repo's **Settings → Actions → General → Workflow
   permissions** must be set to **"Read and write permissions"**. The
   `permissions: contents: write` block in the workflow file requests this,
   but some repos also need the setting enabled directly — otherwise the
   push is rejected and you won't necessarily notice unless you check the
   "Persist alert cooldown state" step in the Actions log.
2. **The universe of qualifying stocks was just very small.** Before this
   update, requiring the MACD crossover on the *exact single day* it happened
   meant very few stocks matched *at all* on any given day — so the same one
   or two names could plausibly be the only ones matching for a while. The
   widened `MACD_CROSSOVER_LOOKBACK_DAYS` window plus the ranking/backfill
   system above should substantially increase how many distinct names show
   up, independent of the cooldown fix.

## "Why did it only scan ~2,000 stocks when I asked for the whole market?"

`SCREENER_LIMIT` (raised to 10,000) is just a ceiling — it was never actually
the bottleneck. Your **`MIN_MARKET_CAP` of $2B** is: that alone excludes the
majority of US small/micro-cap stocks, and ~2,000 is roughly how many
NYSE/NASDAQ names actually clear a $2B market cap plus the price/volume
filters. If you want a genuinely larger slice of "the whole market" (including
small-caps), lower `MIN_MARKET_CAP` in `config.py` — e.g. to `300_000_000` for
small-caps, or `0` to remove the floor entirely. This is a real trade-off
though: the $2B floor was in your original spec specifically to keep the bot
in more liquid, institutional-grade names — removing it will surface more
candidates but also more speculative ones.

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
| `chart_patterns.py` | Multi-bar chart patterns: cup & handle, triangles, flags, double bottom, inverse H&S, VCP (returns breakout levels, not just yes/no) |
| `entry_strategy.py` | Strategic entry: breakout level / volume-profile POC / swing support, instead of always using the raw close |
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
