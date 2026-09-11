# BRIGHTS — Arsitektur (Indeks Dokumentasi)

**BRIGHTS** (BRI Stock Intelligence) adalah mesin analisis kuantitatif untuk emiten Bursa
Efek Indonesia (IDX / BEI): analisis fundamental, valuasi multi-model, teknikal, scoring
5-pilar, high-conviction buy signal, screener, perbandingan, dan kalender makro.

Dokumen ini adalah **pintu masuk**. Detail dipecah ke tiga dokumen:

| Dokumen | Isi |
|---------|-----|
| [TOPOLOGY.md](./TOPOLOGY.md) | Topologi komponen, layering 4-lapis, peta file & modul, topologi sumber data, cache |
| [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) | Kontrak data, pipeline scoring, formula tiap engine, konfigurasi, keterbatasan |
| [FLOWCHARTS.md](./FLOWCHARTS.md) | Diagram Mermaid: alur request, pipeline, resolusi sumber, startup |
| [DATA_SOURCES.md](./DATA_SOURCES.md) | Sumber data & cara konfigurasi (gratis vs berlisensi) |

---

## 1. Sekilas

- **Stack**: FastAPI (Python 3.9) + Uvicorn; frontend static SPA; CLI (typer/rich).
- **Arsitektur**: 4 lapis searah — API → Service → Engine → Data Provider.
- **Data**: real-data-only. Default gratis Yahoo Finance (`yfinance`), opsional Sectors.app & EODHD.
- **Tanpa database**: hanya cache in-memory berumur pendek.
- **Tes**: 51 test (pytest) hijau; sudah diverifikasi live end-to-end di seluruh endpoint.

```
API (FastAPI routers) → Service (orkestrasi) → Engine (compute murni) → Data Provider (I/O)
                                                                              ↓
                                              Yahoo Finance / Sectors.app / EODHD
```

---

## 2. Fitur → Endpoint

| Fitur | Endpoint (`/api/v1`) |
|-------|----------------------|
| Analisis emiten tunggal (skor, valuasi, konviksi, ownership) | `GET /emiten/{ticker}` |
| Cari emiten | `GET /emiten/search?q=` |
| Daftar universe | `GET /emiten/list` |
| Kepemilikan / shareholder | `GET /emiten/{ticker}/shareholders` |
| Perbandingan peer | `POST /compare` |
| Screener multi-faktor + preset | `POST /screener/run`, `GET /screener/presets` |
| Rekomendasi per anggaran harga | `GET /screener/recommend-by-price`, `GET /screener/price-tiers` |
| Ringkasan pasar + Top Picks | `GET /market/summary`, `GET /market/top-picks` |
| Chart + teknikal | `GET /chart/{ticker}` |
| Kurs & konversi USD/IDR | `GET /currency/rate`, `/currency/convert` |
| Kalender makro & sensitivitas sektor | `GET /calendar`, `/calendar/{id}`, `/calendar/sectors/sensitivity` |

---

## 3. Model scoring (ringkas)

```
composite = profitability×0.25 + valuation×0.25 + financial_health×0.20
          + cash_flow_quality×0.15 + growth×0.15          (skala 0–100)
Grade: A+ ≥85 · A ≥75 · B ≥65 · C ≥50 · D ≥35 · F <35
```

Tujuh engine (murni, stateless):

| Engine | Output utama |
|--------|--------------|
| `ScoringEngine` | Orkestrator: radar 5-sumbu, composite, grade, verdict, insight |
| `ValuationEngine` | PER, PBV, P/S, EV/EBITDA, PEG, Graham, DCF / Justified-PBV (bank) |
| `ProfitabilityEngine` | ROE, ROA, ROIC, ROCE, DuPont 3-way, margin |
| `FinancialHealthEngine` | Altman-Z (EM), Piotroski F, Beneish M, growth/CAGR, likuiditas, cashflow/dividen |
| `SectorBankEngine` | Metrik OJK: CAR, NPL, NIM, BOPO, LDR, CASA, CoC + bank health score |
| `ConvictionEngine` | 10-point checklist, Margin of Safety, buy zone, position sizing |
| `TechnicalEngine` | EMA/SMA/RSI, breakout/gap, support/resistance (dipakai chart) |

---

## 4. Sumber data

Prioritas via `DATA_SOURCE_PRIORITY` (default `yfinance,sectors,eodhd`). Sumber pertama yang
memberi data valid menang.

- **Yahoo Finance** (default, gratis, tanpa key): harga (delayed ~15m), fundamental, ownership kasar.
- **Sectors.app** (opsional, berlisensi): fundamental & ownership IDX/KSEI, enumerasi ticker penuh.
- **EODHD** (opsional): harga/fundamental global.
- **idx_universe.py**: 123 ticker IDX kurasi untuk fitur market-wide (override via `IDX_TICKER_UNIVERSE`).

Detail & cara set key: lihat [DATA_SOURCES.md](./DATA_SOURCES.md).

---

## 5. Cara menjalankan

```bash
pip install -r requirements.txt        # termasuk yfinance (gratis, no key)
# jalankan server:
python -m uvicorn app.main:app --reload    # dari dalam folder backend/
# cek: GET http://127.0.0.1:8000/health  → {"status":"healthy"}
# API docs interaktif: /docs
```

Tes:
```bash
python -m pytest -q                    # dari dalam folder backend/
```

---

## 6. Catatan transparansi (penting)

Ini fakta dari kode — perlu diketahui saat menafsirkan output, dirinci di
[SYSTEM_DESIGN.md §8](./SYSTEM_DESIGN.md#8-keterbatasan-yang-diketahui-jujur):

1. Harga Yahoo **delayed ~15 menit**; tidak ada order book / broker summary / foreign flow.
2. Komposisi kepemilikan retail/asing/big-money **presisi tidak tersedia gratis** (butuh KSEI berlisensi).
3. Field `currency.source` bersifat **branding** — sumber sebenarnya bisa sekunder/fallback.
4. Kalender makro **hardcoded** (kurasi manual); fetcher FRED/BPS ada tapi tidak dipanggil.
5. `SectorBankEngine` memakai **default hardcoded** bila metrik bank tak tersedia dari sumber.
6. Top pick **DIVIDEND_CASH_COW** dipilih murni dari yield tertinggi (tanpa syarat skor minimum).

---

## 7. Peta dokumen

```
ARCHITECTURE.md   ← Anda di sini (indeks & overview)
├── TOPOLOGY.md       (komponen, layering, peta file, cache)
├── SYSTEM_DESIGN.md  (kontrak data, pipeline, formula engine, keterbatasan)
├── FLOWCHARTS.md     (diagram Mermaid alur runtime)
└── DATA_SOURCES.md   (konfigurasi sumber data)
```
