# BRIGHTS — Topologi Sistem

> BRIGHTS (BRI Stock Intelligence) — mesin analisis fundamental, valuasi multi-model,
> teknikal, dan scoring untuk emiten Bursa Efek Indonesia (IDX / BEI).
>
> Dokumen ini menggambarkan **topologi komponen** dan **layering**. Untuk detail algoritma
> lihat [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md); untuk alur runtime lihat
> [FLOWCHARTS.md](./FLOWCHARTS.md); ringkasan & indeks di [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## 1. Ringkasan

- **Backend**: FastAPI (Python 3.9), berjalan via Uvicorn.
- **Frontend**: static HTML/CSS/JS single-page (`backend/app/static/`), di-serve oleh FastAPI.
- **Sumber data**: real-data-only. Default gratis = Yahoo Finance (`yfinance`), opsional berlisensi = Sectors.app & EODHD.
- **Tanpa database**: semua state hanya cache in-memory berumur pendek. Tidak ada persistensi.
- **CLI**: ada `backend/cli/` (typer + rich) sebagai antarmuka terminal alternatif.

Prinsip inti: **tidak ada data fiktif**. Jika sumber tidak bisa menyediakan angka, field dibiarkan
`None`/`0.0` atau endpoint mengembalikan `503`, alih-alih mengarang.

---

## 2. Layering (4 lapis)

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRESENTATION            Static SPA (index.html/app.js/app.css)       │
│                          + CLI (typer/rich)                           │
├─────────────────────────────────────────────────────────────────────┤
│  API LAYER               FastAPI routers  (app/api/v1/*.py)           │
│  (HTTP)                  emiten · compare · screener · market ·       │
│                          chart · currency · calendar                  │
├─────────────────────────────────────────────────────────────────────┤
│  SERVICE LAYER           Orkestrasi use-case (app/services/*.py)      │
│  (orchestration)         emiten · market_summary · screener ·         │
│                          comparison · chart · currency · calendar ·   │
│                          ksei                                         │
├─────────────────────────────────────────────────────────────────────┤
│  ENGINE LAYER            Analitik murni / stateless (app/engines/*)   │
│  (pure compute)          scoring · valuation · profitability ·        │
│                          financial_health · sector_bank ·             │
│                          conviction · technical                       │
├─────────────────────────────────────────────────────────────────────┤
│  DATA LAYER              Provider abstraction (app/data_providers/*)  │
│  (I/O eksternal)         InstitutionalDataProvider (orchestrator)     │
│                          → YFinance · Sectors · EODHD                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Yahoo Finance    Sectors.app        EODHD
              (gratis)         (opsional)        (opsional)
```

Aturan dependensi (searah, atas → bawah):
- API layer **hanya** memanggil Service layer.
- Service layer memanggil Engine layer dan Data layer.
- Engine layer **murni** (tanpa I/O, tanpa jaringan) — hanya menerima model & mengembalikan model.
- Data layer satu-satunya yang melakukan I/O jaringan ke sumber eksternal.

---

## 3. Peta modul (topologi file)

```
calculation-emiten/
├── backend/
│   ├── app/
│   │   ├── main.py                 # Entrypoint FastAPI, registrasi router, CORS, static mount
│   │   ├── config.py               # Loader .env sederhana (tanpa dependency)
│   │   │
│   │   ├── api/v1/                  # ── API LAYER ──
│   │   │   ├── emiten.py            # /emiten: analisis, search, list, shareholders
│   │   │   ├── compare.py           # /compare: peer comparison
│   │   │   ├── screener.py          # /screener: run, recommend-by-price, price-tiers, presets
│   │   │   ├── market.py            # /market: summary, top-picks
│   │   │   ├── chart.py             # /chart/{ticker}: OHLCV + teknikal
│   │   │   ├── currency.py          # /currency: rate, convert
│   │   │   └── calendar.py          # /calendar: agenda makro & sensitivitas sektor
│   │   │
│   │   ├── services/                # ── SERVICE LAYER ──
│   │   │   ├── emiten_service.py    # Inti: get_keystats → scoring; cache + threadpool
│   │   │   ├── market_summary_service.py  # Agregasi pasar + Top Picks
│   │   │   ├── screener_service.py  # Filter multi-faktor, preset, price-tier
│   │   │   ├── comparison_service.py# Perbandingan + best-in-class
│   │   │   ├── chart_service.py     # Gabung OHLCV + teknikal + overlay fundamental
│   │   │   ├── currency_service.py  # Kurs USD/IDR multi-sumber + cache
│   │   │   ├── calendar_service.py  # Kalender makro (dataset kurasi)
│   │   │   └── ksei_service.py      # Statistik SID KSEI (butuh URL JSON eksternal)
│   │   │
│   │   ├── engines/                 # ── ENGINE LAYER (pure) ──
│   │   │   ├── scoring_engine.py    # ORCHESTRATOR: composite score, grade, verdict, radar
│   │   │   ├── valuation_engine.py  # PER/PBV/PS/EV-EBITDA/PEG/Graham/DCF/Justified-PBV
│   │   │   ├── profitability_engine.py  # ROE/ROA/ROIC/ROCE/DuPont/margin
│   │   │   ├── financial_health.py  # Altman-Z/Piotroski/Beneish/growth/liquidity/cashflow
│   │   │   ├── sector_bank_engine.py# Metrik OJK: CAR/NPL/NIM/BOPO/LDR/CASA/CoC
│   │   │   ├── conviction_engine.py # 10-point checklist/MoS/buy-zone/position-sizing
│   │   │   └── technical_engine.py  # EMA/SMA/RSI + breakout/gap/support-resistance
│   │   │
│   │   ├── data_providers/          # ── DATA LAYER ──
│   │   │   ├── base.py              # BaseDataProvider (ABC / kontrak)
│   │   │   ├── institutional_provider.py  # Orchestrator sumber (prioritas)
│   │   │   ├── yfinance_provider.py # Yahoo Finance (default, gratis)
│   │   │   ├── sectors_provider.py  # Sectors.app (opsional, berlisensi)
│   │   │   ├── eodhd_provider.py    # EODHD (opsional)
│   │   │   └── idx_universe.py      # Daftar 123 ticker IDX kurasi + override env
│   │   │
│   │   ├── models/                  # Pydantic models (kontrak data antar-layer)
│   │   │   ├── keystats.py          # RawKeyStats, FinancialPeriod, BankSpecificMetrics
│   │   │   ├── score.py             # EmitenAnalysisReport + sub-hasil engine
│   │   │   ├── conviction.py        # BuyConvictionReport + checklist/scenario/sizing
│   │   │   ├── ownership.py         # OwnershipBreakdown, ShareholderEntry, SIDStatistics
│   │   │   ├── chart.py             # CandleDataPoint, TechnicalIndicators, ChartResponse
│   │   │   ├── screener.py          # ScreenerCriteria/Response, EmitenSummaryItem, Comparison
│   │   │   ├── market.py            # MarketSummaryResponse, TopPickItem, MarketOverviewStats
│   │   │   ├── currency.py          # CurrencyRateResponse, CurrencyConversion*
│   │   │   ├── calendar.py          # CalendarResponse, CalendarAgendaItem, dst
│   │   │   ├── financial_matrix.py  # StockbitFinancialMatrix (matriks kuartalan)
│   │   │   └── xbrl.py              # XBRLEntryPoint (general vs banking)
│   │   │
│   │   └── static/                  # Frontend SPA
│   │       ├── index.html
│   │       ├── app.js
│   │       └── app.css
│   │
│   ├── cli/                         # Antarmuka terminal (typer/rich)
│   │   ├── commands.py
│   │   └── terminal_app.py
│   │
│   ├── tests/                       # 51 test (pytest) — api, engines, services
│   └── .env / .env.example          # Konfigurasi (kunci opsional; default gratis)
│
├── requirements.txt
├── DATA_SOURCES.md                  # Dokumentasi sumber data & konfigurasi
├── ARCHITECTURE.md                  # ← indeks dokumentasi arsitektur
├── TOPOLOGY.md                      # ← dokumen ini
├── SYSTEM_DESIGN.md
└── FLOWCHARTS.md
```

---

## 4. Peta endpoint → service → engine/provider

| Endpoint (prefix `/api/v1`)          | Service                    | Engine / Provider utama                          |
|--------------------------------------|----------------------------|--------------------------------------------------|
| `GET /emiten/{ticker}`               | EmitenService              | ScoringEngine (semua engine) + Provider.get_keystats |
| `GET /emiten/search`                 | EmitenService              | Provider.search_tickers                          |
| `GET /emiten/list`                   | EmitenService              | Provider.list_all_tickers (idx_universe)         |
| `GET /emiten/{ticker}/shareholders`  | EmitenService + KSEIService| Provider.get_shareholders                        |
| `POST /compare`                      | ComparisonService          | EmitenService → ScoringEngine                    |
| `POST /screener/run`                 | ScreenerService            | EmitenService.analyze_many (threadpool)          |
| `GET /screener/recommend-by-price`   | ScreenerService            | EmitenService.analyze_many                       |
| `GET /screener/price-tiers`          | ScreenerService            | EmitenService.analyze_many                       |
| `GET /screener/presets`              | ScreenerService            | (statis)                                         |
| `GET /market/summary`                | MarketSummaryService       | EmitenService.analyze_many (universe penuh)      |
| `GET /market/top-picks`              | MarketSummaryService       | (dari summary, cached)                           |
| `GET /chart/{ticker}`                | ChartService               | TechnicalEngine + Provider.get_historical_ohlcv  |
| `GET /currency/rate`, `/convert`     | CurrencyService            | (sumber kurs eksternal, lihat catatan)           |
| `GET /calendar`, `/{id}`, `/sectors/sensitivity` | CalendarService | (dataset kurasi, lihat catatan)                  |

---

## 5. Topologi sumber data (Data Layer)

`InstitutionalDataProvider` adalah **orchestrator** yang memilih sumber berdasarkan
`DATA_SOURCE_PRIORITY` (default `yfinance,sectors,eodhd`). Sumber pertama yang mengembalikan
data valid "menang".

```
                 ┌───────────────────────────────────────┐
                 │      InstitutionalDataProvider         │
                 │  (implements BaseDataProvider)         │
                 │  priority: yfinance,sectors,eodhd      │
                 └───────────────────────────────────────┘
                     │ get_keystats / get_historical_ohlcv
                     │ get_shareholders / list_all_tickers
        ┌────────────┼───────────────────────┐
        ▼            ▼                        ▼
┌──────────────┐ ┌──────────────┐      ┌──────────────┐
│ YFinance     │ │ Sectors.app  │      │ EODHD        │
│ (default,    │ │ (opsional,   │      │ (opsional)   │
│  gratis,     │ │  berlisensi) │      │              │
│  no key)     │ │              │      │              │
└──────────────┘ └──────────────┘      └──────────────┘
   │                                       
   └── idx_universe.py (123 ticker kurasi, override via IDX_TICKER_UNIVERSE)
```

Kontrak `BaseDataProvider` (semua provider mengimplementasikan):
- `get_keystats(ticker, override_price, force_live) -> RawKeyStats | None`
- `get_historical_ohlcv(ticker, timeframe) -> List[CandleDataPoint]`
- `get_shareholders(ticker) -> OwnershipBreakdown | None`
- `list_all_tickers() -> List[str]`
- `search_tickers(query) -> List[RawKeyStats]`
- `get_bulk_market_data() -> Dict` (default: iterasi list_all_tickers)

---

## 6. Cache & konkurensi

Tidak ada database — hanya cache in-memory:

| Lokasi                         | Isi                         | TTL      | Catatan                        |
|--------------------------------|-----------------------------|----------|--------------------------------|
| `EmitenService._report_cache`  | EmitenAnalysisReport/ticker | 5 menit  | class-level, dipakai bulk pass |
| `EmitenService` ThreadPool     | analisis paralel            | —        | 16 worker (I/O-bound yfinance) |
| `YFinanceProvider._*_cache`    | Ticker/info per ticker      | proses   | per instance                   |
| `CurrencyService._cached_rate` | Kurs USD/IDR                | 5 menit  | class-level                    |
| `KSEIStatisticsService._cache` | Statistik SID               | 6 jam    | class-level                    |
| `MarketSummaryService`         | (memakai report cache)      | —        | universe full pass ~15-20s cold |

---

## 7. Catatan jujur (transparansi sumber data)

Hal-hal ini **fakta dari kode**, bukan bug, tapi penting dipahami saat membaca output:

1. **Currency `source` label bersifat branding.** `CurrencyService` mencoba BI JISDOR →
   Frankfurter (ECB) → open.er-api → fallback hardcoded (16.250). Field `source` bisa tetap
   berlabel "Bank Indonesia JISDOR ..." meski data sebenarnya dari sumber sekunder/fallback.

2. **Calendar data hardcoded.** `CalendarService._get_base_dataset()` mengembalikan dataset
   event makro yang dikurasi manual (tanggal 2026). Fetcher FRED & BPS **didefinisikan tapi
   tidak dipanggil** — jadi kalender bukan data live.

3. **SectorBankEngine punya nilai default.** Bila metrik bank (CAR/NPL/NIM/dst) tidak tersedia
   dari sumber, engine memakai angka default hardcoded (mis. CAR 22.5, NPL 2.1). Sementara itu,
   provider yfinance/eodhd sendiri **tidak** memalsukan metrik bank (dibiarkan `None`), sehingga
   perlu diperhatikan: `bank_data` dari engine bisa berisi default meski sumber kosong.

4. **Komposisi kepemilikan foreign/retail/big-money presisi tidak tersedia gratis.** Yang ada
   dari Yahoo hanya proksi kasar (insider %, institution %, free float %) dan akurasinya untuk
   IDX terbatas. Split retail/asing akurat butuh sumber KSEI berlisensi.

5. **Harga Yahoo delayed ~15 menit**, bukan realtime tick. Order book & broker summary tidak tersedia.
