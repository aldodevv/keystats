# BRIGHTS — System Design

> Detail desain sistem: kontrak data, pipeline analisis, formula tiap engine, dan
> keputusan desain. Untuk topologi komponen lihat [TOPOLOGY.md](./TOPOLOGY.md);
> untuk diagram alur lihat [FLOWCHARTS.md](./FLOWCHARTS.md).

---

## 1. Prinsip desain

1. **Real-data-only.** Tidak ada dataset sintetis. Jika sumber tak menyediakan angka, field
   dibiarkan `None`/`0.0`. Orchestrator gagal jelas (`503`) daripada mengarang.
2. **Layer terpisah tegas.** Engine murni (pure function, tanpa I/O), service mengorkestrasi,
   data provider satu-satunya yang menyentuh jaringan.
3. **Provider pluggable.** Menambah sumber data = implement `BaseDataProvider` + daftarkan di
   priority. Tidak menyentuh engine/service.
4. **Stateless compute + cache pendek.** Tanpa DB; cache in-memory berumur pendek untuk
   menekan panggilan jaringan berulang.

---

## 2. Model data inti (kontrak antar-layer)

Aliran transformasi data:

```
Sumber eksternal (JSON/DataFrame)
        │  (Data Provider parsing)
        ▼
RawKeyStats ──────────────────────┐   app/models/keystats.py
  ├── current_period: FinancialPeriod   (revenue, net_income, eps, assets, debt, cfo, ...)
  ├── previous_period: FinancialPeriod   (untuk YoY / Piotroski / Beneish)
  ├── historical_periods: [FinancialPeriod]  (untuk CAGR 3Y)
  ├── financial_matrix: StockbitFinancialMatrix  (kuartalan multi-tahun)
  ├── bank_metrics: BankSpecificMetrics | None
  └── xbrl_entry_point: GENERAL_INDUSTRY | FINANCIAL_BANKING
        │  (ScoringEngine.analyze_emiten)
        ▼
EmitenAnalysisReport ─────────────┐   app/models/score.py
  ├── valuation: ValuationResult
  ├── profitability: ProfitabilityResult
  ├── solvency: SolvencyResult
  ├── liquidity: LiquidityResult
  ├── quality: QualityScoreResult
  ├── cash_flow_dividend: CashFlowDividendResult
  ├── growth: GrowthResult
  ├── bank_metrics: dict | None        (dari SectorBankEngine)
  ├── radar: RadarScore (5 sumbu)
  ├── composite_score, grade, verdict
  ├── bull_cases / bear_cases / green_flags / red_flags
  ├── price_sensitivity_scenarios: [PriceSensitivityScenario]
  ├── buy_conviction: BuyConvictionReport   (app/models/conviction.py)
  └── ownership: OwnershipBreakdown | None  (dilampirkan service)
```

`RawKeyStats` adalah **titik netral**: apa pun sumbernya (Yahoo/Sectors/EODHD), semua
di-normalisasi ke bentuk ini sebelum masuk engine. Inilah yang membuat engine tak peduli
asal data.

---

## 3. Pipeline analisis emiten (ScoringEngine)

`ScoringEngine.analyze_emiten(raw: RawKeyStats) -> EmitenAnalysisReport`
(file `app/engines/scoring_engine.py`).

Urutan eksekusi (penting — ada dependensi antar-langkah):

```
1. ProfitabilityEngine.calculate(raw)                    → prof
2. FinancialHealthEngine.calculate_growth(raw)           → growth   (dihitung DULU)
3. ValuationEngine.calculate(raw, eps_growth=growth.eps_growth_yoy) → val
        (growth dibutuhkan valuasi untuk PEG ratio)
4. calculate_solvency / calculate_liquidity /
   calculate_quality / calculate_cash_flow_dividend      → solv, liq, qual, cf_div
5. Deteksi is_bank → SectorBankEngine.evaluate_bank(raw) → bank_data (jika bank)
6. _compute_radar(...)                                   → RadarScore (5 sumbu, 0-100)
7. composite_score  = Σ (radar × bobot)
8. _determine_grade / _determine_verdict
9. _generate_insights (bull/bear/green/red)
10. _generate_price_sensitivity (-15%..+15%)
11. ConvictionEngine.calculate(...)                      → BuyConvictionReport
→ EmitenAnalysisReport
```

### 3.1 Deteksi bank

`is_bank = True` bila salah satu: `xbrl_entry_point == FINANCIAL_BANKING`, kata `"bank"`/
`"financial"` ada di `sector`, atau `bank_metrics` tidak `None`. Bila bank, sumbu
financial_health pada radar diambil dari `bank_data["bank_health_score"]` (bukan Altman/DER).

### 3.2 Composite Score (bobot)

```
composite = profitability×0.25 + valuation×0.25 + financial_health×0.20
          + cash_flow_quality×0.15 + growth×0.15
```

### 3.3 Radar 5 sumbu (0-100, di-clamp 5..100)

| Sumbu              | Basis skor                                                            |
|--------------------|----------------------------------------------------------------------|
| valuation          | upside/downside %, PER, PBV, PEG                                      |
| profitability      | ROE, NPM, ROIC                                                        |
| financial_health   | Altman zone + DER + net-cash (non-bank) / bank_health_score (bank)   |
| growth             | EPS/revenue YoY + CAGR 3Y                                             |
| cash_flow_quality  | Piotroski F (bobot 35), CFO/NI, FCF yield                            |

### 3.4 Grade & Verdict

Grade: `A+ ≥85`, `A ≥75`, `B ≥65`, `C ≥50`, `D ≥35`, `F <35`.

Verdict (urutan evaluasi):
- `AVOID` bila Altman DISTRESS **atau** risiko manipulasi (Beneish) **atau** score < 40.
- `STRONG_BUY` bila score ≥75 & upside >10% & Piotroski ≥6.
- `BUY` bila score ≥60 & upside ≥0.
- `HOLD` bila score ≥50.
- `SPECULATIVE` selain itu.

---

## 4. Engine reference (formula sesungguhnya)

### 4.1 ValuationEngine (`valuation_engine.py`)

`calculate(raw, eps_growth_rate=None) -> ValuationResult`. Menghitung:

- **PER** = price / EPS
- **PBV** = price / BVPS (BVPS = total_equity / shares)
- **P/S** = market_cap / revenue
- **EV/EBITDA** (non-bank): EV = market_cap + total_debt − cash; EBITDA fallback =
  operating_profit + 5%×total_assets. **Bank**: EV/EBITDA di-set = PER.
- **PEG** = PER / eps_growth_rate (hanya bila growth > 1.0 & PER > 0; else `None`).
- **Graham Number** = √(22.5 × EPS × BVPS) (hanya bila EPS>0 & BVPS>0).
- **DCF / Justified P/B** (`_calculate_dcf`):
  - **Non-bank**: DCF 5 tahun, FCF growth 7%, WACC 10%, terminal growth 3%.
    Base FCF fallback: CFO−|capex|, lalu 0.7×net_income.
  - **Bank**: Justified P/B Gordon = (ROE − g)/(Ke − g), Ke=11%, g=6%, di-clamp 0.8..5.0,
    lalu ×BVPS.
- **Valuation bands** (`_analyze_band`): z-score vs `pe_mean_5y`/`pbv_mean_5y` + std → label
  "Below −1.5σ" ... "Above +1.5σ". `None` bila mean/std tak tersedia.
- **average_fair_value** = rata-rata dari {Graham, DCF, pe_mean×eps, pbv_mean×bvps} yang
  tersedia; fallback BVPS×1.5. **upside_downside_pct** & **is_undervalued** (upside >10%).

### 4.2 ProfitabilityEngine (`profitability_engine.py`)

`calculate(raw) -> ProfitabilityResult`:
- Margin: GPM, OPM, NPM (÷ revenue).
- ROE = NI/equity; ROA = NI/assets.
- **DuPont 3-way**: net_margin (NI/rev) × asset_turnover (rev/assets) × equity_multiplier (assets/equity) = ROE.
- **ROIC** = NOPAT / invested_capital; NOPAT = EBIT×(1−0.22) (tarif pajak Indonesia 22%);
  invested_capital = equity + total_debt − cash. Fallback ke ROE bila invested_capital ≤0.
- **ROCE** = EBIT / (total_assets − current_liabilities). Fallback ROA.

### 4.3 FinancialHealthEngine (`financial_health.py`)

Lima method publik + tiga algoritma internal:

- `calculate_solvency` → **SolvencyResult**: DER = total_debt/equity, net_debt_to_equity,
  ICR = EBIT / (7%×total_debt) *(bunga diestimasi 7% — proxy, bukan bunga aktual)*,
  debt_to_ebitda, Altman-Z + zone. **Bank**: Altman tidak berlaku → z=3.5, zone SAFE.
- `calculate_liquidity` → **LiquidityResult**: current/quick/cash ratio, working capital.
- `calculate_quality` → **QualityScoreResult**: Piotroski F (0-9), CFO/NI, Beneish M-Score.
- `calculate_cash_flow_dividend` → **CashFlowDividendResult**: FCF (fallback CFO−|capex|,
  lalu 0.75×NI), fcf_yield, dividend_yield, DPR, cash coverage, is_sustainable (DPR≤80 & FCF>0).
- `calculate_growth` → **GrowthResult**: revenue/NI/EPS YoY (0.0 bila tak ada prev — tidak
  difabrikasi), CAGR 3Y (butuh ≥3 historical_periods), timeline eps_history & revenue_history.

**Altman Z (Emerging Market model)** — non-manufaktur/umum:
```
Z = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4
  X1 = working_capital/assets   X2 = retained_earnings/assets
  X3 = EBIT/assets              X4 = book_equity/liabilities
Zona: SAFE >2.60 · GREY 1.10–2.60 · DISTRESS <1.10
```

**Piotroski F-Score (9 kriteria)**: 3 kriteria non-YoY (ROA>0, CFO>0, CFO>NI) selalu
dievaluasi; 6 kriteria YoY (ΔROA, leverage, likuiditas, dilusi, margin, asset turnover)
dicatat `False` bila tak ada prior period (tidak fabrikasi prior).

**Beneish M-Score** — versi ringkas 5 variabel (bukan 8 penuh):
```
M = −4.84 + 0.92·DSRI + 0.528·GMI + 0.892·SGI + 0.115·LVGI + 4.679·accruals
manipulasi bila M > −1.78
```
> Catatan: DEPI, SGAI, AQI **tidak** dihitung. `None` bila tak ada prior period.

### 4.4 SectorBankEngine (`sector_bank_engine.py`)

`evaluate_bank(raw) -> dict` (bukan Pydantic). Metrik OJK/BI: CAR, NPL gross/net, NIM, BOPO,
LDR, CASA, Cost of Credit. Setiap metrik: pakai `bank_metrics` bila ada → hitung dari
`current_period` → **default hardcoded** bila tetap kosong (NIM 5.2, LDR 83.5, BOPO 64.0,
CAR 22.5, NPL 2.1/0.6, CASA 68.0, CoC 1.1).

`bank_health_score` = 60 + bonus (CAR≥18 +8, NPL≤2 +10, NIM≥5 +8, BOPO≤70 +8, CASA≥65 +4,
LDR 75-92 +2), clamp ≤100. Menghasilkan juga `bank_strengths` & `bank_flags` (ambang OJK).

> ⚠️ Karena engine ini bisa memakai default, `bank_metrics` di report bank bisa menampilkan
> angka default meski sumber tidak menyediakannya. Provider data sendiri tidak memalsukan.

### 4.5 ConvictionEngine (`conviction_engine.py`)

`calculate(...) -> BuyConvictionReport`:
- **Multi-scenario** (bear/base/bull): base = average_fair_value; bear = rata-rata
  {0.8×Graham, BVPS×(1.1 bank/0.9), 0.75×base} di-cap ≤0.88×base; bull = rata-rata
  {1.25×base, 1.15×DCF, pe_mean×1.2×eps} di-floor ≥1.15×base. Hitung MoS, downside, upside,
  risk/reward.
- **Buy Zone**: MoS ≥25% STRONG_ACCUMULATION · ≥10% MODERATE_BUY · ≥−5% FAIR_HOLD · else OVERVALUED_TRIM.
- **10-point checklist**: (1) EPS growth 3Y≥8% atau YoY≥10%, (2) ROE≥14% bank/12% non-bank,
  (3) CFO/NI≥1.0 (atau ≥0.85 & FCF>0), (4) valuasi PER≤15 atau upside≥10% atau Graham-safe,
  (5) solvency bank CAR≥18% & NPL≤3.5% / non-bank Altman SAFE & DER≤1.5, (6) Beneish aman,
  (7) FCF yield≥3.5% atau FCF>0, (8) div yield≥2.5% & DPR≤85%/sustainable, (9) NPM≥8% atau
  GPM≥25%, (10) MoS≥15%. `conviction_score = passed/10 × 100`.
- **Tier**: ≥8 HIGH · ≥5 MODERATE · ≥3 LOW · else AVOID.
- **Position sizing**: HIGH+A/A+ →20%, MODERATE/B →10%, LOW →5%, AVOID →0%; TP1=base, TP2=bull,
  stop_loss = min(bear×0.95, price×0.90) + invalidation triggers.

### 4.6 TechnicalEngine (`technical_engine.py`) — dipakai ChartService, BUKAN scoring

`analyze(candles) -> (indicators, signals, support_resistance, gaps)`. Butuh ≥5 candle.
- **Indikator**: EMA-20 (n≥20), SMA-50 (fallback SMA-20), SMA-200 (fallback SMA-100),
  RSI-14 (Wilder smoothing, n≥15, default 50). Plus `trend_summary` & `momentum_summary`.
  > Catatan: docstring menyebut MACD, tapi **MACD tidak diimplementasikan**.
- **Signals**: Breakout Buy (close > high-20d + volume ≥1.35×avg), Breakdown Sell, Gap Up/Down
  (≥1.5%). Maks 15 sinyal terbaru.
- **Support/Resistance**: swing high/low 5-hari → cluster (toleransi 2%), maks 8 level.
- **Gaps**: gap up/down + status `is_filled`, 6 terbaru.

---

## 5. Fitur pasar (market-wide)

### 5.1 Top Picks (MarketSummaryService)

Analisis seluruh universe (via `analyze_many`, paralel + cached), lalu pilih 4 kategori berbeda
(ticker tidak boleh dobel antar kategori):
1. **TOP_PICK_OVERALL** — composite tertinggi + upside>0 + Piotroski≥6.
2. **BEST_VALUE** — upside>10% & Altman Z≥1.8, urut upside.
3. **HIGH_QUALITY_MOAT** — ROE≥15% & Piotroski≥7.
4. **DIVIDEND_CASH_COW** — dividend yield≥3.5%, urut yield.

> ⚠️ Kategori DIVIDEND_CASH_COW dipilih murni dari yield tertinggi tanpa syarat skor minimum,
> sehingga bisa memilih emiten berskor rendah. Ini perilaku desain saat ini.

### 5.2 Screener (ScreenerService)

`run_screener(criteria)` → filter universe by kriteria (PER, PBV, ROE, DER, score, harga,
dividend, sektor, verdict). Preset: BUFFETT_MOAT, DIVIDEND_CASH_COW, GARP, DEEP_VALUE,
MOMENTUM_QUALITY, AFFORDABLE_GEMS, UNDERVALUED_DEALS. Plus `recommend-by-price` & `price-tiers`
(Budget <1.000 / Mid 1.000-5.000 / Premium >5.000).

---

## 6. Performa: konkurensi & cache

Masalah awal: market summary loop 123 ticker × ~6 panggilan yfinance = bermenit-menit (timeout).

Solusi di `EmitenService`:
- `analyze_many(tickers)` — `ThreadPoolExecutor(max_workers=16)` (yfinance I/O-bound).
- `_report_cache` (class-level, TTL 5 menit) — cache hasil analisis + cache miss (None) agar
  ticker gagal tidak di-hit berulang.
- Hasil: universe penuh **cold ~15-20s**, **cached instan**.

---

## 7. Konfigurasi (env)

| Env var                 | Default                    | Fungsi                                        |
|-------------------------|----------------------------|-----------------------------------------------|
| `DATA_SOURCE_PRIORITY`  | `yfinance,sectors,eodhd`   | Urutan prioritas sumber                       |
| `SECTORS_API_KEY`       | (kosong)                   | Aktifkan Sectors.app (opsional)               |
| `EODHD_API_KEY`         | (kosong / `demo`=off)      | Aktifkan EODHD (opsional)                     |
| `IDX_TICKER_UNIVERSE`   | (kosong → 123 kurasi)      | Override daftar ticker (comma-separated)      |
| `KSEI_STATISTICS_URL`   | (kosong)                   | Endpoint JSON statistik SID KSEI (opsional)   |
| `FRED_API_KEY`          | (kosong)                   | Terdefinisi tapi tidak dipakai di alur aktif  |
| `BPS_API_KEY`           | (kosong)                   | Terdefinisi tapi tidak dipakai di alur aktif  |

---

## 8. Keterbatasan yang diketahui (jujur)

1. Harga Yahoo **delayed ~15 menit**; tidak ada order book / broker summary / foreign flow.
2. Komposisi kepemilikan retail/asing/big-money **presisi tidak tersedia gratis** (butuh KSEI berlisensi).
3. `currency.source` bersifat branding; sumber sebenarnya bisa sekunder/fallback.
4. Calendar **hardcoded** (kurasi manual), bukan feed live; FRED/BPS terdefinisi tapi tak dipanggil.
5. `SectorBankEngine` memakai **default hardcoded** untuk metrik bank yang tidak tersedia.
6. ICR memakai estimasi bunga 7%×debt (proxy), bukan beban bunga aktual.
7. Tanpa database — semua non-persisten; cache hilang saat proses restart.
