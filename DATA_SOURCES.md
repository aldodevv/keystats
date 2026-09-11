# BRIGHTS — Data Sources & Configuration

BRIGHTS (BRI Stock Intelligence) is **real-data-only**. It never fabricates or ships mock
financial data. When no data source is reachable, API endpoints return `503` with a clear
message instead of inventing numbers.

By default BRIGHTS runs on a **free, public, no-API-key** source (Yahoo Finance), so it
works out of the box for personal use with IDX (BEI) emitens.

## Quick start (free, no keys)

```bash
pip install -r requirements.txt        # installs yfinance (free Yahoo Finance client)
# no API keys needed — just run the app
```

That's it. All fundamentals, prices, and ownership come from public Yahoo Finance data for
`.JK` tickers (e.g. `BBRI`, `ASII`, `ADRO`).

## Configured sources (in priority order)

Priority is controlled by the `DATA_SOURCE_PRIORITY` environment variable
(comma-separated). Default: `yfinance,sectors,eodhd`.

### 1. Yahoo Finance — default, free, public, no API key
- Uses the open-source [`yfinance`](https://github.com/ranaroussi/yfinance) library to read
  the same public data shown on finance.yahoo.com for IDX tickers (suffix `.JK`).
- Provides: live/EOD price, previous close, day change %, shares outstanding, market cap,
  multi-year fundamentals (income statement, balance sheet, cash flow in IDR),
  corporate-action adjusted historical OHLCV, and holder composition where Yahoo exposes it.
- No configuration required. This is the recommended source for personal / self-consumption
  use of IDX data.
- Note: Yahoo has no free "list every IDX symbol" endpoint. To keep market-wide features
  (Top Picks, screener, IDX summary) working, BRIGHTS bundles a curated universe of **real
  IDX ticker codes** (LQ45/IDX80 + other liquid emitens) in
  `backend/app/data_providers/idx_universe.py`. These are public identifiers only — every
  emiten's actual figures are still fetched **live** from Yahoo; nothing is fabricated.
  Override or extend the list with the `IDX_TICKER_UNIVERSE` env var (comma-separated codes,
  e.g. `IDX_TICKER_UNIVERSE="BBRI,ASII,TLKM"`). A licensed source (below) provides full
  automatic enumeration if you'd rather not maintain the list.
- Performance: market-wide passes analyze the universe concurrently and cache results for
  5 minutes, so the first market-summary load takes ~15-20s and subsequent loads are instant.

> Content was rephrased for compliance with licensing restrictions. yfinance is a free,
> open-source library that downloads market data from Yahoo Finance. See the
> [project page](https://github.com/ranaroussi/yfinance) and
> [docs](https://ranaroussi.github.io/yfinance/).

### 2. Sectors.app (Supertype) — optional, licensed
- Licensed Indonesian financial-data platform. Fundamentals and shareholder/ownership data
  sourced from **IDX and KSEI** filings, kept current beyond 2024.
- Adds full IDX ticker enumeration and bulk screening that Yahoo cannot provide for free.
- Endpoint: `https://api.sectors.app/v2/` — Auth header `Authorization: <API_KEY>`
- Configure: `export SECTORS_API_KEY="your_key"` — Get a key: https://sectors.app

### 3. EODHD — optional, prices / fundamentals
- Global fundamentals plus realtime quotes and split/dividend-adjusted OHLCV.
- Configure: `export EODHD_API_KEY="your_key"` (the placeholder `demo` is treated as unset)
- Get a key: https://eodhd.com

> **Free-plan limitation:** an EODHD *free* key returns **EOD prices only** — no
> fundamentals and no shareholder data, ~1 year history, ~20 requests/day. Use Yahoo Finance
> (default) or Sectors.app for fundamentals/ownership instead.

### KSEI SID statistics (optional enrichment)
- Market-wide Single Investor Identification (SID) counts from KSEI.
- Configure: `export KSEI_STATISTICS_URL="https://your-proxy/ksei-sid.json"`
- Expected JSON: `{"total_sid": 14200000, "equity_sid": 6100000, "as_of_date": "2026-07-31"}`

> **Note:** `https://web.ksei.co.id/publications/Data_Statistik_KSEI` is a **JS-rendered HTML
> page, not a JSON API** — its underlying data endpoints are not publicly addressable, so
> BRIGHTS cannot read it directly. Point `KSEI_STATISTICS_URL` at a JSON endpoint. Until then
> SID shows as "unavailable" rather than being fabricated.

## Example

```bash
# Free default — nothing to configure. Optionally add licensed sources:
export SECTORS_API_KEY="..."       # optional: full IDX enumeration + IDX/KSEI ownership
export EODHD_API_KEY="..."         # optional: alternate prices / adjusted OHLCV
export KSEI_STATISTICS_URL="..."   # optional: retail SID statistics
export DATA_SOURCE_PRIORITY="yfinance,sectors,eodhd"   # optional: override precedence
```

## Why not scrape idx.co.id directly?

`idx.co.id` is protected by Cloudflare bot management and returns `403` to programmatic
clients. Bypassing that protection violates IDX's Terms of Service. BRIGHTS therefore uses
only **public / permitted** sources: free Yahoo Finance by default, plus optional licensed
feeds (Sectors.app, EODHD) and an operator-provided KSEI feed. The authoritative raw IDX
feed that member brokers use requires a commercial IDX data license.
