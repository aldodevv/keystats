# BRIGHTS — Flowcharts & Diagram Alur

> Diagram runtime memakai sintaks [Mermaid](https://mermaid.js.org/) (dirender otomatis di
> GitHub, VS Code + ekstensi Mermaid, dan banyak viewer Markdown). Untuk komponen statis lihat
> [TOPOLOGY.md](./TOPOLOGY.md); untuk formula lihat [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md).

---

## 1. Arsitektur berlapis (high-level)

```mermaid
flowchart TD
    subgraph P[Presentation]
        SPA[Static SPA<br/>index.html / app.js]
        CLI[CLI<br/>typer + rich]
    end

    subgraph A[API Layer - FastAPI routers]
        EMI[/emiten/]
        CMP[/compare/]
        SCR[/screener/]
        MKT[/market/]
        CHT[/chart/]
        CUR[/currency/]
        CAL[/calendar/]
    end

    subgraph S[Service Layer]
        ES[EmitenService]
        MSS[MarketSummaryService]
        SS[ScreenerService]
        CS[ComparisonService]
        CHS[ChartService]
        CUS[CurrencyService]
        CAS[CalendarService]
        KS[KSEIService]
    end

    subgraph E[Engine Layer - pure compute]
        SCE[ScoringEngine]
        VE[ValuationEngine]
        PE[ProfitabilityEngine]
        FH[FinancialHealthEngine]
        SB[SectorBankEngine]
        CE[ConvictionEngine]
        TE[TechnicalEngine]
    end

    subgraph D[Data Layer]
        IDP[InstitutionalDataProvider<br/>orchestrator]
        YF[YFinanceProvider]
        SEC[SectorsProvider]
        EOD[EODHDProvider]
    end

    subgraph X[External]
        YAHOO[(Yahoo Finance)]
        SAPP[(Sectors.app)]
        EODHD[(EODHD)]
    end

    SPA --> A
    CLI --> S
    EMI --> ES
    CMP --> CS
    SCR --> SS
    MKT --> MSS
    CHT --> CHS
    CUR --> CUS
    CAL --> CAS

    CS --> ES
    SS --> ES
    MSS --> ES
    CHS --> ES
    ES --> SCE
    ES --> KS

    SCE --> VE & PE & FH & SB & CE
    CHS --> TE

    ES --> IDP
    IDP --> YF & SEC & EOD
    YF --> YAHOO
    SEC --> SAPP
    EOD --> EODHD
```

---

## 2. Analisis emiten tunggal — `GET /emiten/{ticker}`

```mermaid
sequenceDiagram
    participant C as Client
    participant API as emiten router
    participant ES as EmitenService
    participant IDP as InstitutionalDataProvider
    participant SRC as Source (yfinance/sectors/eodhd)
    participant SCE as ScoringEngine
    participant KS as KSEIService

    C->>API: GET /emiten/PTBA?live=true
    API->>ES: analyze_single_emiten(PTBA)
    ES->>IDP: get_keystats(PTBA)
    loop sumber sesuai prioritas
        IDP->>SRC: get_keystats
        SRC-->>IDP: RawKeyStats | None
        Note over IDP: menang jika revenue > 0
    end
    IDP-->>ES: RawKeyStats
    alt RawKeyStats kosong
        ES-->>API: None
        API-->>C: 404 not found
    else ada data
        ES->>SCE: analyze_emiten(raw)
        SCE-->>ES: EmitenAnalysisReport
        ES->>IDP: get_shareholders(PTBA)
        IDP-->>ES: OwnershipBreakdown | None
        ES->>KS: get_market_sid()
        KS-->>ES: SIDStatistics | None
        ES-->>API: report (+ ownership)
        API-->>C: 200 EmitenAnalysisReport
    end
```

---

## 3. Pipeline scoring internal (ScoringEngine.analyze_emiten)

```mermaid
flowchart TD
    RAW[RawKeyStats] --> PROF[ProfitabilityEngine.calculate]
    RAW --> GROWTH[FinancialHealthEngine.calculate_growth]
    GROWTH -->|eps_growth_yoy| VAL[ValuationEngine.calculate]
    RAW --> VAL
    RAW --> SOLV[calculate_solvency]
    RAW --> LIQ[calculate_liquidity]
    RAW --> QUAL[calculate_quality<br/>Piotroski + Beneish]
    RAW --> CFD[calculate_cash_flow_dividend]

    RAW --> ISBANK{is_bank?}
    ISBANK -->|ya| BANK[SectorBankEngine.evaluate_bank]
    ISBANK -->|tidak| SKIP[bank_data = None]

    PROF & VAL & SOLV & GROWTH & QUAL & CFD & BANK --> RADAR[_compute_radar<br/>5 sumbu 0-100]
    RADAR --> COMP[composite_score<br/>25/25/20/15/15]
    COMP --> GRADE[_determine_grade]
    COMP --> VERDICT[_determine_verdict]

    PROF & VAL & SOLV & QUAL & CFD & GROWTH --> INS[_generate_insights<br/>bull/bear/green/red]
    COMP --> PSS[_generate_price_sensitivity<br/>-15% .. +15%]
    COMP & GRADE --> CONV[ConvictionEngine.calculate<br/>10-point checklist + MoS + sizing]

    GRADE & VERDICT & RADAR & INS & PSS & CONV --> REPORT[EmitenAnalysisReport]
```

---

## 4. Resolusi sumber data (InstitutionalDataProvider)

```mermaid
flowchart TD
    START[get_keystats / OHLCV / shareholders] --> PRIO{Baca DATA_SOURCE_PRIORITY}
    PRIO --> LIST[Susun sumber ter-konfigurasi<br/>yfinance selalu aktif tanpa key]
    LIST --> EMPTY{Ada sumber?}
    EMPTY -->|tidak| ERR[raise DataSourceNotConfiguredError -> 503]
    EMPTY -->|ya| LOOP[Iterasi sumber sesuai urutan]
    LOOP --> TRY[Panggil sumber ke-i]
    TRY --> OK{Data valid?}
    OK -->|ya| RET[Return data - sumber pertama menang]
    OK -->|tidak| NEXT{Masih ada sumber?}
    NEXT -->|ya| LOOP
    NEXT -->|tidak| NONE[Return None / list kosong]
```

---

## 5. Market summary & Top Picks — `GET /market/summary`

```mermaid
sequenceDiagram
    participant C as Client
    participant API as market router
    participant MSS as MarketSummaryService
    participant ES as EmitenService
    participant POOL as ThreadPool (16)
    participant CACHE as _report_cache (TTL 5m)

    C->>API: GET /market/summary
    API->>MSS: get_market_summary()
    MSS->>ES: list_all_available_tickers()
    ES-->>MSS: ~123 ticker (idx_universe)
    MSS->>ES: analyze_many(tickers)
    par konkuren
        ES->>POOL: submit _cached_report(ticker) x N
        POOL->>CACHE: cek cache
        alt cache hit
            CACHE-->>POOL: report
        else cache miss
            POOL->>ES: analyze_single_emiten (no ownership)
            ES-->>CACHE: simpan (report / None)
        end
    end
    POOL-->>ES: kumpulan report
    ES-->>MSS: List[report]
    MSS->>MSS: hitung stats + pilih 4 Top Picks
    MSS-->>API: MarketSummaryResponse
    API-->>C: 200 (stats, top_picks, emitens[])
```

Pemilihan Top Picks (4 kategori distinct):

```mermaid
flowchart LR
    R[Reports] --> P1[TOP_PICK_OVERALL<br/>composite tinggi + upside>0 + F>=6]
    R --> P2[BEST_VALUE<br/>upside>10% + Altman>=1.8]
    R --> P3[HIGH_QUALITY_MOAT<br/>ROE>=15% + F>=7]
    R --> P4[DIVIDEND_CASH_COW<br/>yield>=3.5%]
    P1 --> U{ticker sudah dipakai?}
    P2 --> U
    P3 --> U
    P4 --> U
    U -->|belum| PICKS[Daftar Top Picks]
```

---

## 6. Chart — `GET /chart/{ticker}`

```mermaid
sequenceDiagram
    participant C as Client
    participant API as chart router
    participant CHS as ChartService
    participant IDP as Provider
    participant TE as TechnicalEngine
    participant ES as EmitenService

    C->>API: GET /chart/BBRI?timeframe=6mo
    API->>CHS: get_chart_data(BBRI, 6mo)
    CHS->>IDP: get_historical_ohlcv(BBRI, 6mo)
    IDP-->>CHS: List[CandleDataPoint]
    alt candle kosong
        CHS-->>API: None
        API-->>C: 404
    else ada candle
        CHS->>TE: analyze(candles)
        TE-->>CHS: indicators, signals, S/R, gaps
        CHS->>ES: analyze_single_emiten(BBRI)
        ES-->>CHS: report (untuk overlay TP1/TP2/bear floor)
        CHS-->>API: ChartResponse
        API-->>C: 200 (candles + indikator + overlay)
    end
```

---

## 7. Currency — fallback berjenjang

```mermaid
flowchart TD
    REQ[get_live_rate] --> CACHE{cache < 5 menit?}
    CACHE -->|ya| RET[Return cache]
    CACHE -->|tidak| S1[BI JISDOR<br/>bi.go.id/biweb/api/kurs-jisdor]
    S1 -->|gagal / rate<=5000| S2[Frankfurter ECB<br/>api.frankfurter.app]
    S2 -->|gagal| S3[open.er-api.com]
    S3 -->|gagal| FB[Fallback hardcoded 16.250]
    S1 -->|ok| BUILD[Bangun CurrencyRateResponse]
    S2 -->|ok| BUILD
    S3 -->|ok| BUILD
    FB --> BUILD
    BUILD --> SAVE[Simpan cache] --> RET2[Return]
```

> Catatan: field `source` bisa berlabel "Bank Indonesia JISDOR ..." meski data dari sumber
> sekunder/fallback (branding, bukan jaminan sumber).

---

## 8. Startup aplikasi

```mermaid
flowchart TD
    START[uvicorn app.main:app] --> ENV[import app.config<br/>load .env]
    ENV --> APP[Buat FastAPI + CORS]
    APP --> ROUTERS[Registrasi 7 router /api/v1]
    ROUTERS --> STATIC[Mount /static]
    STATIC --> READY[Siap: GET /health -> healthy]
```

---

## 9. Boundary data eksternal (apa live vs statis)

```mermaid
flowchart LR
    subgraph LIVE[Live dari jaringan]
        Y[Yahoo Finance<br/>harga delayed ~15m, fundamental, ownership]
        FX[Kurs USD/IDR<br/>JISDOR/ECB/OER]
        SIDJSON[KSEI SID<br/>hanya jika URL diisi]
    end
    subgraph STATIC[Statis / kurasi di kode]
        UNI[idx_universe<br/>123 ticker]
        CALDATA[Calendar dataset<br/>hardcoded 2026]
        BANKDEF[Bank metric defaults<br/>bila sumber kosong]
    end
    subgraph OPT[Opsional berlisensi]
        SECD[Sectors.app]
        EODD[EODHD]
    end
```
