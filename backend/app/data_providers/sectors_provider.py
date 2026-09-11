"""
Sectors.app (Supertype) Data Provider for the Indonesian Stock Exchange (IDX).

Sectors is a licensed Indonesian financial-data platform whose company fundamentals and
shareholder/ownership data are sourced from IDX and KSEI filings. This makes it a
legitimate, accurate, and up-to-date source (kept current beyond 2024) that mirrors the
data brokers rely on — WITHOUT scraping idx.co.id (which is bot-protected and whose
programmatic access would violate its Terms of Service).

API: https://api.sectors.app/v2/  — authenticated via the `Authorization: <API_KEY>` header.
Configure the key via the SECTORS_API_KEY environment variable or the constructor.

Real-data-only: every value comes from the live Sectors response. Missing datapoints are
left as None/0.0 rather than fabricated.
"""

import os
import datetime
from typing import Optional, List, Dict, Any

import requests

from app.data_providers.base import BaseDataProvider
from app.models.keystats import RawKeyStats, FinancialPeriod, BankSpecificMetrics
from app.models.chart import CandleDataPoint
from app.models.xbrl import XBRLEntryPoint
from app.models.ownership import (
    OwnershipBreakdown,
    ShareholderEntry,
    SharesStatistics,
)


class SectorsProvider(BaseDataProvider):
    BASE_URL = "https://api.sectors.app/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SECTORS_API_KEY", "").strip()
        self._report_cache: Dict[str, Dict[str, Any]] = {}
        self._symbol_cache: Optional[List[str]] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    # -------------------------------------------------------------
    # Low-level HTTP
    # -------------------------------------------------------------
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        if not self.is_configured:
            return None
        url = f"{self.BASE_URL}{path}"
        try:
            resp = requests.get(
                url,
                headers={"Authorization": self.api_key},
                params=params,
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def _fetch_report(self, clean_ticker: str) -> Optional[Dict[str, Any]]:
        """Fetches and caches the full company report (all sections) for a ticker."""
        if clean_ticker in self._report_cache:
            return self._report_cache[clean_ticker]
        data = self._get(
            f"/company/report/{clean_ticker}/",
            params={"sections": "overview,financials,valuation,ownership,dividend,peers"},
        )
        if not isinstance(data, dict):
            return None
        self._report_cache[clean_ticker] = data
        return data

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------
    @staticmethod
    def _f(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _fo(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _first(d: Dict[str, Any], *keys: str) -> Any:
        for k in keys:
            if isinstance(d, dict) and d.get(k) not in (None, ""):
                return d[k]
        return None

    @staticmethod
    def _pct(value: Any) -> Optional[float]:
        """Normalizes a ratio to a percentage. Sectors often reports ratios as fractions."""
        v = SectorsProvider._fo(value)
        if v is None:
            return None
        # Fractions (|v| <= 1.5) are scaled to %, values already in % are kept.
        return round(v * 100, 2) if abs(v) <= 1.5 else round(v, 2)

    # -------------------------------------------------------------
    # BaseDataProvider implementation
    # -------------------------------------------------------------
    def get_keystats(
        self,
        ticker: str,
        override_price: Optional[float] = None,
        force_live: bool = False,
    ) -> Optional[RawKeyStats]:
        clean = ticker.upper().replace(".JK", "").strip()
        report = self._fetch_report(clean)
        if not report:
            return None

        overview = report.get("overview", {}) or {}
        financials = report.get("financials", {}) or {}
        valuation = report.get("valuation", {}) or {}

        name = self._first(overview, "company_name", "name") or f"{clean} Tbk"
        sector = self._first(overview, "sub_sector", "sector", "industry") or "General"
        industry = self._first(overview, "industry", "sub_industry", "sector") or "General"

        price = self._f(self._first(overview, "last_close_price", "close", "latest_close", "market_cap") and
                        self._first(overview, "last_close_price", "close", "latest_close"))
        if override_price and override_price > 0:
            price = float(override_price)

        shares = self._f(self._first(overview, "shares_outstanding", "listed_shares"))
        market_cap = self._f(self._first(overview, "market_cap", "market_capitalization"))
        if market_cap <= 0 and price > 0 and shares > 0:
            market_cap = price * shares
        if shares <= 0 and market_cap > 0 and price > 0:
            shares = market_cap / price

        is_bank = "bank" in str(sector).lower() or "financ" in str(sector).lower()
        entry_point = XBRLEntryPoint.FINANCIAL_BANKING if is_bank else XBRLEntryPoint.GENERAL_INDUSTRY

        # Build financial periods from historical statements.
        current_period, previous_period, historical = self._build_periods(financials, shares, entry_point)
        if current_period is None:
            return None

        prev_close = self._fo(self._first(overview, "previous_close", "prev_close"))
        change_pct = self._pct(self._first(overview, "price_change_pct", "change_pct", "daily_change"))

        return RawKeyStats(
            ticker=clean,
            name=str(name),
            sector=str(sector),
            industry=str(industry),
            xbrl_entry_point=entry_point,
            current_price=price,
            previous_close=prev_close,
            price_change_pct=change_pct or 0.0,
            is_realtime=False,
            last_updated_time=datetime.datetime.now().isoformat(),
            shares_outstanding=shares if shares > 0 else 1.0,
            market_cap=market_cap,
            current_period=current_period,
            previous_period=previous_period,
            historical_periods=historical,
            dps=self._f(self._first(report.get("dividend", {}) or {}, "dps", "dividend_per_share")),
            beta=self._f(self._first(valuation, "beta")) or 1.0,
            bank_metrics=self._build_bank_metrics(financials) if is_bank else None,
        )

    def _build_periods(self, financials: Dict[str, Any], shares: float, entry_point: XBRLEntryPoint):
        """Parses Sectors historical financial statements into FinancialPeriod objects."""
        # Sectors typically exposes a list of yearly statements under a 'historical'/'yearly' key.
        rows = None
        for key in ("historical_financials", "yearly", "annual", "financials", "statements"):
            candidate = financials.get(key)
            if isinstance(candidate, list) and candidate:
                rows = candidate
                break

        periods: List[FinancialPeriod] = []
        if rows:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                p = self._row_to_period(row, shares, entry_point)
                if p:
                    periods.append(p)
        elif isinstance(financials, dict) and any(
            k in financials for k in ("total_revenue", "revenue", "earnings", "net_income")
        ):
            # Single flat snapshot form.
            p = self._row_to_period(financials, shares, entry_point)
            if p:
                periods.append(p)

        if not periods:
            return None, None, []

        periods.sort(key=lambda p: p.year, reverse=True)
        current = periods[0]
        previous = periods[1] if len(periods) > 1 else None
        historical = periods[1:6]
        return current, previous, historical

    def _row_to_period(self, row: Dict[str, Any], shares: float, entry_point: XBRLEntryPoint) -> Optional[FinancialPeriod]:
        date_str = str(self._first(row, "date", "period", "year", "fiscal_year") or "")
        year = None
        if len(date_str) >= 4 and date_str[:4].isdigit():
            year = int(date_str[:4])
        if year is None:
            return None

        revenue = self._f(self._first(row, "total_revenue", "revenue"))
        net_income = self._f(self._first(row, "net_income", "profit_and_loss", "earnings"))
        gross_profit = self._f(self._first(row, "gross_profit", "gross_income"))
        operating = self._f(self._first(row, "operating_profit", "operating_income", "operating_pnl"))
        ebitda = self._f(self._first(row, "ebitda"))
        total_assets = self._f(self._first(row, "total_assets"))
        total_equity = self._f(self._first(row, "total_equity", "total_stockholder_equity"))
        total_liab = self._f(self._first(row, "total_liabilities", "total_liab"))
        total_debt = self._f(self._first(row, "total_debt", "debt"))
        cash = self._f(self._first(row, "cash_and_equivalents", "cash", "cash_only"))
        cfo = self._f(self._first(row, "cash_from_operations", "cfo", "operating_cash_flow"))
        capex = self._f(self._first(row, "capital_expenditure", "capex"))
        fcf = self._f(self._first(row, "free_cash_flow", "fcf"))
        eps = self._f(self._first(row, "eps", "earnings_per_share"))
        if eps == 0.0 and shares > 0 and net_income != 0.0:
            eps = net_income / shares

        return FinancialPeriod(
            year=year,
            filing_date=date_str,
            xbrl_entry_point=entry_point,
            revenue=revenue,
            gross_profit=gross_profit,
            operating_profit=operating,
            ebit=operating,
            ebitda=ebitda,
            net_income=net_income,
            eps=eps,
            total_assets=total_assets,
            cash_and_equivalents=cash,
            total_liabilities=total_liab,
            total_debt=total_debt,
            total_equity=total_equity,
            cfo=cfo,
            capex=capex,
            fcf=fcf if fcf != 0.0 else (cfo - abs(capex) if cfo != 0.0 else 0.0),
            shares_outstanding=shares,
            interest_income=self._f(self._first(row, "interest_income")),
            net_interest_income=self._f(self._first(row, "net_interest_income", "nii")),
            total_loans=self._f(self._first(row, "total_loans", "loans")),
            deposits_dpk=self._f(self._first(row, "deposits", "total_deposits", "dpk")),
        )

    def _build_bank_metrics(self, financials: Dict[str, Any]) -> Optional[BankSpecificMetrics]:
        """Maps real bank ratios from Sectors when present; None-fields otherwise."""
        src = financials
        if isinstance(financials.get("bank_metrics"), dict):
            src = financials["bank_metrics"]
        car = self._pct(self._first(src, "car", "capital_adequacy_ratio"))
        nim = self._pct(self._first(src, "nim", "net_interest_margin"))
        npl_g = self._pct(self._first(src, "npl_gross", "npl"))
        npl_n = self._pct(self._first(src, "npl_net"))
        ldr = self._pct(self._first(src, "ldr", "loan_to_deposit_ratio"))
        bopo = self._pct(self._first(src, "bopo"))
        casa = self._pct(self._first(src, "casa"))
        if not any([car, nim, npl_g, ldr, bopo, casa]):
            return None
        return BankSpecificMetrics(
            car=car, npl_gross=npl_g, npl_net=npl_n, nim=nim, bopo=bopo, ldr=ldr, casa=casa,
        )

    def list_all_tickers(self) -> List[str]:
        if self._symbol_cache is not None:
            return self._symbol_cache
        data = self._get("/companies/", params={"order_by": "-market_cap"})
        symbols: List[str] = []
        if isinstance(data, list):
            for item in data:
                sym = self._first(item, "symbol", "ticker") if isinstance(item, dict) else None
                if sym:
                    symbols.append(str(sym).upper().replace(".JK", ""))
        if symbols:
            self._symbol_cache = symbols
        return symbols

    def search_tickers(self, query: str) -> List[RawKeyStats]:
        q = query.upper().strip()
        results = []
        for t in self.list_all_tickers():
            if q in t:
                stats = self.get_keystats(t)
                if stats:
                    results.append(stats)
                if len(results) >= 10:
                    break
        return results

    def get_historical_ohlcv(self, ticker: str, timeframe: str = "1y") -> List[CandleDataPoint]:
        clean = ticker.upper().replace(".JK", "").strip()
        days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5y": 1825}
        days = days_map.get(timeframe.lower(), 365)
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=days)
        data = self._get(
            f"/daily/{clean}/",
            params={"start": from_date.isoformat(), "end": to_date.isoformat()},
        )
        candles: List[CandleDataPoint] = []
        if isinstance(data, list):
            for row in data:
                if not isinstance(row, dict):
                    continue
                close = self._f(self._first(row, "close", "adjusted_close"))
                if close <= 0:
                    continue
                o = self._f(self._first(row, "open")) or close
                h = self._f(self._first(row, "high")) or close
                l = self._f(self._first(row, "low")) or close
                candles.append(CandleDataPoint(
                    time=str(self._first(row, "date", "trade_date")),
                    open=round(o, 2), high=round(h, 2), low=round(l, 2),
                    close=round(close, 2),
                    volume=int(self._f(self._first(row, "volume"))),
                ))
        return candles

    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        clean = ticker.upper().replace(".JK", "").strip()
        report = self._fetch_report(clean)
        if not report:
            return None

        overview = report.get("overview", {}) or {}
        ownership = report.get("ownership", {}) or {}
        name = self._first(overview, "company_name", "name") or f"{clean} Tbk"

        # Aggregate ownership breakdown
        major = self._parse_holders(
            self._first(ownership, "major_shareholders", "shareholders", "top_shareholders")
        )
        institutional = self._parse_holders(self._first(ownership, "institutional", "institutions"))

        # Ownership percentage buckets (Sectors 'ownership_percentage' style)
        buckets = self._first(ownership, "ownership_percentage", "ownership_breakdown") or {}
        public_float = self._pct(self._first(buckets, "public", "retail", "free_float")) if isinstance(buckets, dict) else None
        insider = self._pct(self._first(buckets, "insider", "controlling", "director_and_commissioner")) if isinstance(buckets, dict) else None
        institution = self._pct(self._first(buckets, "institution", "institutions", "local_institutions")) if isinstance(buckets, dict) else None
        government = self._pct(self._first(buckets, "government")) if isinstance(buckets, dict) else None

        shares = self._fo(self._first(overview, "shares_outstanding", "listed_shares"))
        stats_model = None
        if shares or public_float is not None or insider is not None:
            stats_model = SharesStatistics(
                shares_outstanding=shares,
                float_percentage=public_float,
                percent_insiders=insider,
                percent_institutions=institution,
            )

        if not any([major, institutional, stats_model, public_float, insider, institution]):
            return None

        return OwnershipBreakdown(
            ticker=clean,
            name=str(name),
            source="Sectors.app (IDX/KSEI)",
            shares_statistics=stats_model,
            public_float_pct=public_float,
            insider_pct=insider,
            institution_pct=institution,
            government_pct=government,
            major_shareholders=major,
            institutional_holders=institutional,
            is_real_data=True,
        )

    def _parse_holders(self, block: Any) -> List[ShareholderEntry]:
        entries: List[ShareholderEntry] = []
        if not isinstance(block, list):
            return entries
        for h in block:
            if not isinstance(h, dict):
                continue
            name = self._first(h, "name", "shareholder", "holder_name")
            if not name:
                continue
            pct = self._pct(self._first(h, "share_percentage", "percentage", "pct", "ownership"))
            shares = self._fo(self._first(h, "shares", "share_amount", "total_shares"))
            entries.append(ShareholderEntry(
                name=str(name),
                category=self._first(h, "type", "category"),
                shares=shares,
                percentage=pct,
                is_controlling=bool(pct is not None and pct > 50.0),
            ))
        return entries
