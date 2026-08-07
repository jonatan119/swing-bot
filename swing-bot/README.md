# Swing Trade Alert Bot

Scans the US stock market twice a day (market open + close) against your
strategy rules, and posts matches straight to a Discord channel via webhook.
Runs entirely in the cloud on GitHub Actions — no server, no laptop required.

## Strategy implemented

**Part 1 — Quality filtering (Finviz-style gatekeepers)**
1. Market cap ≥ $2B, price ≥ $5.
2. **Both** current-day volume AND the 20-day average volume must independently
   clear 500K shares/day (not just one or the other).
3. US markets only (NYSE/NASDAQ/AMEX exchange filter + explicit `country=US`
   on the FMP screener, so foreign-domiciled ADRs are excluded too).
4. Analyst consensus must be Buy or Strong Buy.

**Part 2 — Refined entry timing (no chasing)**
- Trend: price > 50 EMA > 150 SMA > 200 SMA.
- Momentum: MACD crossed bullish within the last `MACD_CROSSOVER_LOOKBACK_DAYS`
  (default 3 sessions) and hasn't rolled back over.
- Price action: a bullish candlestick pattern, a chart-pattern breakout
  (Cup and Handle, Ascending Triangle, Bull Flag, Double Bottom, Inverse
  Head and Shoulders, VCP), **or a POC Volume Test** — price holding at the
  volume-profile Point of Control (the single most heavily-traded price
  level recently) with today's volume elevated (`VOLUME_SPIKE_MIN`). This is
  a standalone trigger in its own right, not just a fallback entry
  reference — a stock returning to its heaviest-traded level with real
  participation is a legitimate signal even with no candlestick or chart
  pattern present.
- Volume: day's volume ≥ 120% of the 20-day average.
- **Anti-chasing gate**: today's price change must fall between
  `MIN_DAY_GAIN_PCT` and `MAX_DAY_GAIN_PCT` (default **0.5%–2.5%**). A stock
  already up 5–8% on the day has already been chased by everyone else — this
  only lets through subtle, early-stage confirmations of the move.
- Relative Strength vs SPY (6-month return must beat the market).
- Earnings-date awareness (skip if reporting within `EARNINGS_BLACKOUT_DAYS`).

**Part 3 — Dynamic risk/reward (no more fixed 1:2)**
- **Entry** is strategic, not just today's close: Resistance Breakout (chart
  pattern's own breakout level + buffer) → POC Support Hold → Support Bounce
  → Unconfirmed fallback, in that priority order.
- **Stale-breakout reclassification**: the bot's pattern data is EOD-only,
  but scans run during market hours, so a "fresh breakout" can already be
  old news by the time you see it. If live price has moved more than
  `SUPPORT_RETEST_RECLASSIFY_PCT` (default 1%) beyond a Resistance Breakout
  entry — but not so far that it fails the freshness check entirely — the
  alert relabels it **"Support Retest (former resistance)"** instead of
  presenting a stale breakout price as if it were still actionable at that
  level.
- **Stop-loss** = nearest swing support level (with a small buffer below it),
  or an ATR-based fallback if no clear support exists. The ATR multiplier
  itself **slides between 1.0x–1.5x** based on the stock's own ATR% (see
  `compute_atr_stop_multiplier` in `position_sizing.py`) — calm, low-ATR
  stocks get up to 1.5x of room, volatile high-ATR stocks get tightened
  down to 1.0x, instead of one fixed multiplier for every stock regardless
  of volatility. Whichever result is *tighter* also respects a hard
  `MAX_STOP_LOSS_PCT` cap (default 5%).
- **Take-profit** = the next real swing resistance level above entry; if
  none exists, a **measured-move projection** (the matched pattern's own
  height added above the breakout — e.g. cup depth, flag pole height,
  head-and-shoulders depth) as a more realistic fallback than a flat ATR
  multiple; ATR-based projection only as the last resort.
- **Gatekeeper**: the resulting R:R is calculated from those *real* levels —
  if it comes in below `MIN_RR_RATIO` (default **1:1.5**), the setup is
  **rejected outright**, no alert sent, no exceptions. This replaces the old
  fixed 1:2 ratio with one grounded in actual chart structure.

**Everything else already in the bot:**
- Market regime filter (no alerts while SPY is below its own 200-day SMA).
- Signal scoring (0-100) with a guaranteed minimum result count per scan
  (ranks every candidate and backfills down to `ABSOLUTE_MIN_SCORE` so a
  quiet day doesn't mean 0-2 alerts).
- 14-day alert cooldown per symbol (persisted across runs via GitHub Actions
  cache — see below).
- TradingView chart snapshot per alert (via chart-img.com, optional).
- Position sizing (off by default — `ENABLE_POSITION_SIZING` in `config.py`).

All analysis runs on the **daily (1D) timeframe** — this is fixed in
`config.TIMEFRAME`, not an intraday scanner.

Every rule, weight, and threshold lives in `config.py` — change numbers
there, no need to touch the scanning logic.

## Alert deduplication (no repeat alerts)

Once a symbol triggers an alert, it won't alert again for
`config.ALERT_COOLDOWN_DAYS` (default 14 days) even if you re-run the scan
or it still matches. This state lives in `state/alerted_symbols.json` and
persists across runs via **GitHub Actions cache** (not a git commit back to
the repo — an earlier version of this bot tried that approach, but it kept
silently failing due to repo write-permission requirements and push
conflicts between overlapping runs). The cache-based approach needs no
special repo settings and has no push/conflict failure mode. You won't see
any extra commits in your repo history — that's expected now.

If you ever want to manually clear the cooldown (e.g. to test with a symbol
you know should alert), go to your repo's **Actions tab → Caches** (in the
left sidebar) and delete the `swing-bot-state-*` entries.

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

(You'll see 4 cron entries in the workflow file — an EDT and EST version of
each run, since GitHub Actions cron doesn't shift for daylight saving. A
**"Check if this trigger matches the current DST season"** step runs first
and skips the rest of the job entirely if this particular trigger isn't the
one for the current season — so only one of each pair actually executes the
full scan. This isn't just a cosmetic skip: the EDT/EST pair for each slot
fires only ~1 hour apart, but a full scan takes ~2.5 hours, so without this
guard both would run **at the same time**, both starting from the same
cooldown state, and both independently alerting on the same matches before
either one's update saved — this was the actual cause of repeated alerts on
the same symbol within the cooldown window, not a persistence failure.)

The **"Run workflow"** button under the Actions tab is only for manual test
runs — it's not required for the bot to work day-to-day.

## Troubleshooting: "I keep seeing the same stocks every scan"

1. **Check the cache is actually restoring.** The workflow log has a "Show
   restored state" step that prints the current cooldown file's contents at
   the start of every run — if it says "No prior state file found" on every
   single run (not just the very first one), the cache isn't persisting and
   is worth reporting back with the log so we can dig further. Under normal
   operation you should see it printing an actual list of symbols + dates
   after the first run.
2. **The universe of qualifying stocks was just very small.** Before an
   earlier update, requiring the MACD crossover on the *exact single day* it
   happened meant very few stocks matched *at all* on any given day — so the
   same one or two names could plausibly be the only ones matching for a
   while. The widened `MACD_CROSSOVER_LOOKBACK_DAYS` window plus the
   ranking/backfill system above should substantially increase how many
   distinct names show up, independent of the cooldown mechanism.

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
| `position_sizing.py` | Dynamic stop-loss/take-profit + R:R gatekeeper (structure-based, not fixed ratio), plus optional share sizing |
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
- **Rejection diagnostics**: the scan log now prints a breakdown of exactly
  where candidates fell out (e.g. `rr_below_minimum: 340`, `day_gain_outside_band: 812`,
  `no_pattern: 1500`) instead of just a pass/fail count. If output feels low
  on a given day, check this breakdown first — it tells you which gate is
  the actual binding constraint rather than guessing.
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
