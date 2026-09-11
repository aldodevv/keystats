"""
Deterministic in-memory stub data provider for the test suite.

This is NOT production mock data: it lives only under tests/, is never imported by the
application, and exists solely so unit/integration tests can exercise analysis logic
without a live network data source. Production code refuses to fabricate data.
"""

from typing import Optional, List, Dict, Any

from app.data_providers.base import BaseDataProvider
from app.models.keystats import RawKeyStats, FinancialPeriod, BankSpecificMetrics
from app.models.chart import CandleDataPoint
from app.models.xbrl import XBRLEntryPoint
from app.models.ownership import OwnershipBreakdown, ShareholderEntry, SharesStatistics


def _period(year: int, scale: float, filing: str) -> FinancialPeriod:
    return FinancialPeriod(
        year=year,
        filing_date=filing,
        revenue=100_000 * scale,
        gross_profit=45_000 * scale,
        operating_profit=30_000 * scale,
        ebit=30_000 * scale,
        ebitda=34_000 * scale,
        net_income=28_800 * scale,
        eps=288.0 * scale,
        total_assets=250_000 * scale,
        current_assets=120_000 * scale,
        cash_and_equivalents=40_000 * scale,
        inventory=15_000 * scale,
        receivables=18_000 * scale,
        total_liabilities=90_000 * scale,
        current_liabilities=60_000 * scale,
        total_debt=40_000 * scale,
        short_term_debt=15_000 * scale,
        long_term_debt=25_000 * scale,
        total_equity=160_000 * scale,
        retained_earnings=100_000 * scale,
        cfo=25_000 * scale,
        capex=6_000 * scale,
        fcf=19_000 * scale,
        dividends_paid=8_000 * scale,
        shares_outstanding=100.0,
    )


def _build(ticker: str, name: str, sector: str, price: float, is_bank: bool = False) -> RawKeyStats:
    curr = _period(2024, 1.0, "2025-02-01")
    prev = _period(2023, 0.9, "2024-02-01")
    hist = [
        _period(2023, 0.9, "2024-02-01"),
        _period(2022, 0.82, "2023-02-01"),
        _period(2021, 0.74, "2022-02-01"),
    ]
    bank_metrics = None
    entry = XBRLEntryPoint.GENERAL_INDUSTRY
    if is_bank:
        entry = XBRLEntryPoint.FINANCIAL_BANKING
        bank_metrics = BankSpecificMetrics(
            car=22.0, npl_gross=2.0, npl_net=0.5, nim=5.5, bopo=60.0,
            ldr=82.0, casa=70.0, cost_of_credit=1.0,
        )
    return RawKeyStats(
        ticker=ticker,
        name=name,
        sector=sector,
        industry=sector,
        xbrl_entry_point=entry,
        current_price=price,
        previous_close=price * 0.99,
        price_change_pct=1.0,
        shares_outstanding=100.0,
        market_cap=price * 100.0,
        current_period=curr,
        previous_period=prev,
        historical_periods=hist,
        dps=80.0,
        beta=1.0,
        bank_metrics=bank_metrics,
    )


class StubDataProvider(BaseDataProvider):
    """Returns a small, deterministic universe of realistic-shaped emitens for tests."""

    def __init__(self):
        self._db: Dict[str, RawKeyStats] = {
            "BBRI": _build("BBRI", "Bank Rakyat Indonesia Tbk", "Financials", 2500.0, is_bank=True),
            "BBCA": _build("BBCA", "Bank Central Asia Tbk", "Financials", 9500.0, is_bank=True),
            "BMRI": _build("BMRI", "Bank Mandiri Tbk", "Financials", 6000.0, is_bank=True),
            "ASII": _build("ASII", "Astra International Tbk", "Industrials", 5200.0),
            "TLKM": _build("TLKM", "Telkom Indonesia Tbk", "Communication", 3200.0),
            "ICBP": _build("ICBP", "Indofood CBP Tbk", "Consumer Staples", 11000.0),
            "KLBF": _build("KLBF", "Kalbe Farma Tbk", "Healthcare", 1600.0),
            "ADRO": _build("ADRO", "Alamtri Resources Tbk", "Energy", 2400.0),
            "PTBA": _build("PTBA", "Bukit Asam Tbk", "Energy", 2800.0),
            "CTRA": _build("CTRA", "Ciputra Development Tbk", "Real Estate", 1200.0),
        }

    def get_keystats(self, ticker, override_price=None, force_live=False) -> Optional[RawKeyStats]:
        clean = ticker.upper().replace(".JK", "").strip()
        data = self._db.get(clean)
        if not data:
            return None
        data = data.model_copy(deep=True)
        if override_price and override_price > 0:
            data.current_price = float(override_price)
            data.market_cap = float(override_price * data.shares_outstanding)
        return data

    def list_all_tickers(self) -> List[str]:
        return list(self._db.keys())

    def search_tickers(self, query: str) -> List[RawKeyStats]:
        q = query.upper().strip()
        return [d.model_copy(deep=True) for t, d in self._db.items() if q in t or q in d.name.upper()]

    def get_historical_ohlcv(self, ticker: str, timeframe: str = "1y") -> List[CandleDataPoint]:
        base = self._db.get(ticker.upper().replace(".JK", "").strip())
        price = base.current_price if base else 1000.0
        candles = []
        for i in range(60):
            p = price * (1.0 + (i % 5 - 2) * 0.01)
            candles.append(CandleDataPoint(
                time=f"2024-0{(i % 9) + 1}-01",
                open=round(p * 0.99, 2), high=round(p * 1.01, 2),
                low=round(p * 0.98, 2), close=round(p, 2), volume=1_000_000 + i,
            ))
        return candles

    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        clean = ticker.upper().replace(".JK", "").strip()
        if clean not in self._db:
            return None
        return OwnershipBreakdown(
            ticker=clean,
            name=self._db[clean].name,
            source="STUB",
            shares_statistics=SharesStatistics(
                shares_outstanding=100.0, shares_float=45.0, float_percentage=45.0,
                percent_insiders=55.0, percent_institutions=30.0,
            ),
            public_float_pct=45.0,
            insider_pct=55.0,
            institution_pct=30.0,
            institutional_holders=[
                ShareholderEntry(name="Example Asset Mgmt", category="Institution", percentage=12.5),
            ],
            is_real_data=False,
            notes=["Test fixture data."],
        )
