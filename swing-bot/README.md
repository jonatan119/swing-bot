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
5. **Risk management**: stop-loss = entry − 1.5×ATR(14); take-profit set for
   a 1:2 reward-to-risk ratio.

Every rule and threshold lives in `config.py` — change numbers there, no need
to touch the scanning logic.

## 1. Get an FMP API key

1. Sign up at https://financialmodelingprep.com
2. Free tier works for testing with a handful of tickers. For scanning the
   **full** US market twice a day you'll want a paid plan (roughly $15–30/mo)
   for higher rate limits — the free tier will throttle mid-scan.
3. Copy your API key.

## 2. Create a Discord webhook

1. In your Discord server: Server Settings → Integrations → Webhooks → New Webhook.
2. Pick the channel, copy the Webhook URL.

## 3. Push this project to a GitHub repo

```bash
cd swing-bot
git init
git add .
git commit -m "Swing trade alert bot"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 4. Add your secrets to the repo

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `FMP_API_KEY` | your Financial Modeling Prep key |
| `DISCORD_WEBHOOK_URL` | your Discord webhook URL |

## 5. That's it

The workflow in `.github/workflows/scan.yml` runs automatically at ~market
open and ~market close on weekdays. You can also trigger a manual test run
any time from the repo's **Actions** tab → "Swing Trade Scanner" → **Run workflow**.

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
