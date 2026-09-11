"""
Institutional Data Provider for Indonesian Stock Exchange (IDX / .JK) via EODHD API.
Provides corporate action-adjusted historical OHLCV, comprehensive multi-year fundamentals,
XBRL-mapped financial statements, and single-roundtrip bulk market queries.
"""

import os
import datetime
from typing import Optional, List, Dict, Any
import requests

from app.data_providers.base import BaseDataProvider
from app.models.keystats import RawKeyStats, FinancialPeriod, BankSpecificMetrics
from app.models.chart import CandleDataPoint
from app.models.ownership import (
    OwnershipBreakdown,
    ShareholderEntry,
    SharesStatistics,
    SIDStatistics,
)
from app.models.financial_matrix import (
    StockbitFinancialMatrix,
    QuarterlyDataPoint,
    IncomeStatementTTM,
    BalanceSheetQuarter,
    PerShareFinancials
)
from app.models.xbrl import XBRLEntryPoint, XBRLTaxonomyRegistry


class EODHDProvider(BaseDataProvider):
    BASE_URL = "https://eodhd.com/api"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("EODHD_API_KEY", "demo")
        self._cache: Dict[str, RawKeyStats] = {}
        self._fundamentals_cache: Dict[str, Dict[str, Any]] = {}
        self._bulk_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._bulk_cache_time: Optional[datetime.datetime] = None
        self._symbol_cache: Optional[List[str]] = None

    def _fetch_fundamentals_raw(self, clean_ticker: str) -> Optional[Dict[str, Any]]:
        """Fetches and caches the raw EODHD /fundamentals JSON for a ticker."""
        if clean_ticker in self._fundamentals_cache:
            return self._fundamentals_cache[clean_ticker]

        symbol = f"{clean_ticker}.JK"
        url = f"{self.BASE_URL}/fundamentals/{symbol}?api_token={self.api_key}"
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data or not isinstance(data, dict):
                return None
            self._fundamentals_cache[clean_ticker] = data
            return data
        except Exception:
            return None

    def get_keystats(
        self,
        ticker: str,
        override_price: Optional[float] = None,
        force_live: bool = False
    ) -> Optional[RawKeyStats]:
        clean_ticker = ticker.upper().replace(".JK", "").strip()
        
        if not force_live and not override_price and clean_ticker in self._cache:
            return self._cache[clean_ticker]
            
        try:
            stats = self._fetch_fundamentals_eodhd(clean_ticker)
            if stats:
                if override_price and override_price > 0:
                    stats.current_price = float(override_price)
                    stats.market_cap = float(override_price * stats.shares_outstanding)
                self._cache[clean_ticker] = stats
                return stats
        except Exception:
            pass
            
        return None

    def _fetch_fundamentals_eodhd(self, clean_ticker: str) -> Optional[RawKeyStats]:
        symbol = f"{clean_ticker}.JK"
        data = self._fetch_fundamentals_raw(clean_ticker)
        if not data:
            return None
            
        general = data.get("General", {})
        highlights = data.get("Highlights", {})
        valuation = data.get("Valuation", {})
        financials = data.get("Financials", {})
        
        name = general.get("Name") or f"{clean_ticker} Tbk"
        sector = general.get("Sector") or "General"
        industry = general.get("Industry") or "General"
        
        # Real-time / EOD Price
        realtime_url = f"{self.BASE_URL}/real-time/{symbol}?fmt=json&api_token={self.api_key}"
        price = 0.0
        prev_close = None
        price_change_pct = 0.0
        is_live = False
        
        try:
            rt_resp = requests.get(realtime_url, timeout=3)
            if rt_resp.status_code == 200:
                rt_data = rt_resp.json()
                price = float(rt_data.get("close") or rt_data.get("previousClose") or 0.0)
                prev_close = float(rt_data.get("previousClose") or price)
                price_change_pct = float(rt_data.get("change_p") or 0.0)
                is_live = True
        except Exception:
            pass
            
        if price <= 0:
            price = float(highlights.get("LatestClose") or valuation.get("TrailingPE") or 1000.0)
            
        shares = float(highlights.get("SharesOutstanding") or general.get("SharesOutstanding") or 1.0)
        market_cap = float(highlights.get("MarketCapitalization") or (price * shares))
        
        # Detect XBRL Entry Point
        is_bank = "bank" in sector.lower() or "bank" in industry.lower() or "financial" in sector.lower()
        entry_point = XBRLEntryPoint.FINANCIAL_BANKING if is_bank else XBRLEntryPoint.GENERAL_INDUSTRY
        
        # Parse Financial Statements
        income_yearly = financials.get("Income_Statement", {}).get("yearly", {})
        balance_yearly = financials.get("Balance_Sheet", {}).get("yearly", {})
        cashflow_yearly = financials.get("Cash_Flow", {}).get("yearly", {})
        
        income_quarterly = financials.get("Income_Statement", {}).get("quarterly", {})
        balance_quarterly = financials.get("Balance_Sheet", {}).get("quarterly", {})
        cashflow_quarterly = financials.get("Cash_Flow", {}).get("quarterly", {})
        
        # Build Periods
        yearly_dates = sorted(list(income_yearly.keys()), reverse=True)
        current_period = None
        previous_period = None
        historical_periods = []
        
        if yearly_dates:
            current_period = self._extract_period_from_dict(
                yearly_dates[0],
                income_yearly.get(yearly_dates[0], {}),
                balance_yearly.get(yearly_dates[0], {}),
                cashflow_yearly.get(yearly_dates[0], {}),
                shares=shares,
                entry_point=entry_point
            )
            
            if len(yearly_dates) > 1:
                previous_period = self._extract_period_from_dict(
                    yearly_dates[1],
                    income_yearly.get(yearly_dates[1], {}),
                    balance_yearly.get(yearly_dates[1], {}),
                    cashflow_yearly.get(yearly_dates[1], {}),
                    shares=shares,
                    entry_point=entry_point
                )
                
            for d in yearly_dates[1:6]:
                hp = self._extract_period_from_dict(
                    d,
                    income_yearly.get(d, {}),
                    balance_yearly.get(d, {}),
                    cashflow_yearly.get(d, {}),
                    shares=shares,
                    entry_point=entry_point
                )
                if hp:
                    historical_periods.append(hp)
                    
        if not current_period:
            current_period = FinancialPeriod(
                year=datetime.datetime.now().year,
                revenue=float(highlights.get("RevenueTTM") or 1.0),
                net_income=float(highlights.get("NetIncomeTTM") or 1.0),
                eps=float(highlights.get("DilutedEpsTTM") or 1.0),
                shares_outstanding=shares
            )

        # Build Stockbit Financial Matrix
        matrix = self._build_financial_matrix(income_quarterly, balance_quarterly, cashflow_quarterly, shares, price)
        
        # Bank metrics if banking
        bank_metrics = None
        if is_bank and current_period:
            bank_metrics = self._extract_bank_metrics(current_period, balance_yearly, income_yearly)
            
        return RawKeyStats(
            ticker=clean_ticker,
            name=name,
            sector=sector,
            industry=industry,
            xbrl_entry_point=entry_point,
            current_price=price,
            previous_close=prev_close,
            price_change_pct=price_change_pct,
            is_realtime=is_live,
            last_updated_time=datetime.datetime.now().isoformat(),
            shares_outstanding=shares,
            market_cap=market_cap,
            current_period=current_period,
            previous_period=previous_period,
            historical_periods=historical_periods,
            financial_matrix=matrix,
            dps=float(highlights.get("DividendShare") or 0.0),
            beta=float(highlights.get("Beta") or 1.0),
            bank_metrics=bank_metrics
        )

    def _extract_period_from_dict(
        self,
        date_str: str,
        inc: Dict[str, Any],
        bal: Dict[str, Any],
        cf: Dict[str, Any],
        shares: float,
        entry_point: XBRLEntryPoint
    ) -> FinancialPeriod:
        year = int(date_str[:4]) if len(date_str) >= 4 and date_str[:4].isdigit() else datetime.datetime.now().year
        
        rev = float(inc.get("totalRevenue") or inc.get("revenue") or inc.get("grossIncome") or 0.0)
        gp = float(inc.get("grossProfit") or inc.get("netInterestIncome") or rev * 0.4)
        op = float(inc.get("operatingIncome") or inc.get("operatingProfit") or 0.0)
        ebit = float(inc.get("ebit") or op)
        ebitda = float(inc.get("ebitda") or (ebit * 1.15 if ebit > 0 else 0.0))
        ni = float(inc.get("netIncome") or inc.get("netIncomeCommonStock") or 0.0)
        eps = float(inc.get("eps") or (ni / shares if shares > 0 else 0.0))
        
        tot_assets = float(bal.get("totalAssets") or 0.0)
        cur_assets = float(bal.get("totalCurrentAssets") or (tot_assets * 0.4))
        cash = float(bal.get("cashAndCashEquivalents") or bal.get("cash") or 0.0)
        inv = float(bal.get("inventory") or 0.0)
        rec = float(bal.get("netReceivables") or 0.0)
        
        tot_liab = float(bal.get("totalLiab") or bal.get("totalLiabilities") or 0.0)
        cur_liab = float(bal.get("totalCurrentLiabilities") or (tot_liab * 0.5))
        st_debt = float(bal.get("shortTermDebt") or bal.get("shortLongTermDebt") or 0.0)
        lt_debt = float(bal.get("longTermDebt") or 0.0)
        tot_debt = float(bal.get("shortLongTermDebtTotal") or (st_debt + lt_debt))
        
        tot_equity = float(bal.get("totalStockholderEquity") or bal.get("totalEquity") or 0.0)
        ret_earnings = float(bal.get("retainedEarnings") or (tot_equity * 0.6))
        
        cfo = float(cf.get("totalCashFromOperatingActivities") or 0.0)
        capex = float(cf.get("capitalExpenditures") or 0.0)
        fcf = float(cf.get("freeCashFlow") or (cfo - abs(capex) if cfo != 0 else ni * 0.7))
        div_paid = float(cf.get("dividendsPaid") or 0.0)
        
        return FinancialPeriod(
            year=year,
            filing_date=date_str,
            xbrl_entry_point=entry_point,
            revenue=rev,
            gross_profit=gp,
            operating_profit=op,
            ebit=ebit,
            ebitda=ebitda,
            net_income=ni,
            eps=eps,
            total_assets=tot_assets,
            current_assets=cur_assets,
            cash_and_equivalents=cash,
            inventory=inv,
            receivables=rec,
            total_liabilities=tot_liab,
            current_liabilities=cur_liab,
            total_debt=tot_debt,
            short_term_debt=st_debt,
            long_term_debt=lt_debt,
            total_equity=tot_equity,
            retained_earnings=ret_earnings,
            cfo=cfo,
            capex=capex,
            fcf=fcf,
            dividends_paid=abs(div_paid),
            shares_outstanding=shares
        )

    def _extract_bank_metrics(
        self,
        curr: FinancialPeriod,
        balance_dict: Dict[str, Any],
        income_dict: Dict[str, Any]
    ) -> Optional[BankSpecificMetrics]:
        """
        Derives OJK / Bank Indonesia banking ratios ONLY from real reported line items.

        Generic fundamentals feeds do not expose OJK-specific disclosures such as NPL, CAR,
        CASA or cost-of-credit for IDX banks; those are left as None rather than fabricated.
        NIM and LDR are computed only when the underlying real figures are reported.
        Returns None when no real banking line items are available at all.
        """
        earning_assets = curr.earning_assets if curr.earning_assets > 0 else None
        total_loans = curr.total_loans if curr.total_loans > 0 else None
        dpk = curr.deposits_dpk if curr.deposits_dpk > 0 else None
        net_interest_income = curr.net_interest_income if curr.net_interest_income > 0 else None

        nim = None
        if net_interest_income and earning_assets:
            nim = round(net_interest_income / earning_assets * 100, 2)

        ldr = None
        if total_loans and dpk:
            ldr = round(total_loans / dpk * 100, 2)

        casa = None
        if curr.casa_deposits > 0 and dpk:
            casa = round(curr.casa_deposits / dpk * 100, 2)

        car = None
        if curr.regulatory_capital > 0 and curr.risk_weighted_assets > 0:
            car = round(curr.regulatory_capital / curr.risk_weighted_assets * 100, 2)

        npl_gross = None
        if curr.npl_gross_amount > 0 and total_loans:
            npl_gross = round(curr.npl_gross_amount / total_loans * 100, 2)

        npl_net = None
        if curr.npl_net_amount > 0 and total_loans:
            npl_net = round(curr.npl_net_amount / total_loans * 100, 2)

        # If no real banking line items are present, do not emit a fabricated metrics block.
        if not any([earning_assets, total_loans, dpk, net_interest_income, car]):
            return None

        return BankSpecificMetrics(
            car=car,
            npl_gross=npl_gross,
            npl_net=npl_net,
            nim=nim,
            bopo=None,
            ldr=ldr,
            casa=casa,
            cost_of_credit=None,
            earning_assets=earning_assets,
            total_loans=total_loans,
            deposits_dpk=dpk,
        )

    def _build_financial_matrix(
        self,
        income_q: Dict[str, Any],
        balance_q: Dict[str, Any],
        cf_q: Dict[str, Any],
        shares: float,
        price: float
    ) -> Optional[StockbitFinancialMatrix]:
        """
        Builds a multi-year quarterly matrix from REAL EODHD quarterly statements.
        Each reported quarter is placed in its calendar quarter slot; missing quarters stay None.
        Returns None when no real quarterly data is available.
        """
        if not income_q:
            return None

        def _q_slot(month: int) -> str:
            if month <= 3:
                return "q1"
            if month <= 6:
                return "q2"
            if month <= 9:
                return "q3"
            return "q4"

        net_income_matrix: Dict[str, QuarterlyDataPoint] = {}
        eps_matrix: Dict[str, QuarterlyDataPoint] = {}
        revenue_matrix: Dict[str, QuarterlyDataPoint] = {}
        years_seen = set()

        for date_str, inc in income_q.items():
            if not isinstance(inc, dict) or len(date_str) < 7:
                continue
            try:
                year = date_str[:4]
                month = int(date_str[5:7])
            except (ValueError, IndexError):
                continue
            if not year.isdigit():
                continue

            years_seen.add(int(year))
            slot = _q_slot(month)

            rev = inc.get("totalRevenue") or inc.get("revenue")
            ni = inc.get("netIncome") or inc.get("netIncomeCommonStock")

            net_income_matrix.setdefault(year, QuarterlyDataPoint())
            revenue_matrix.setdefault(year, QuarterlyDataPoint())
            eps_matrix.setdefault(year, QuarterlyDataPoint())

            if ni is not None:
                ni_val = float(ni)
                setattr(net_income_matrix[year], slot, ni_val)
                if shares > 0:
                    setattr(eps_matrix[year], slot, round(ni_val / shares, 2))
            if rev is not None:
                setattr(revenue_matrix[year], slot, float(rev))

        if not years_seen:
            return None

        years = sorted(years_seen, reverse=True)
        return StockbitFinancialMatrix(
            years=years,
            currency="IDR",
            net_income_matrix=net_income_matrix,
            eps_matrix=eps_matrix,
            revenue_matrix=revenue_matrix,
        )

    def get_historical_ohlcv(self, ticker: str, timeframe: str = "1y") -> List[CandleDataPoint]:
        """
        Fetches split and dividend adjusted daily historical OHLCV candles from EODHD.
        Adjusted close prevents artificial chart gaps and false EMA/SMA crossover signals.
        """
        clean_ticker = ticker.upper().replace(".JK", "").strip()
        symbol = f"{clean_ticker}.JK"
        
        # Calculate from/to dates based on timeframe
        days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5y": 1825}
        days = days_map.get(timeframe.lower(), 365)
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=days)
        
        url = f"{self.BASE_URL}/eod/{symbol}?fmt=json&from={from_date.isoformat()}&to={to_date.isoformat()}&period=d&api_token={self.api_key}"
        
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 5:
                    candles: List[CandleDataPoint] = []
                    for row in data:
                        adj_close = float(row.get("adjusted_close") or row.get("close") or 0.0)
                        raw_close = float(row.get("close") or 1.0)
                        adj_ratio = adj_close / raw_close if raw_close > 0 else 1.0
                        
                        o = float(row.get("open") or 0.0) * adj_ratio
                        h = float(row.get("high") or 0.0) * adj_ratio
                        l = float(row.get("low") or 0.0) * adj_ratio
                        c = adj_close
                        v = int(float(row.get("volume") or 0))
                        
                        if o > 0 and c > 0:
                            candles.append(CandleDataPoint(
                                time=str(row.get("date")),
                                open=round(o, 2),
                                high=round(h, 2),
                                low=round(l, 2),
                                close=round(c, 2),
                                volume=v
                            ))
                    if len(candles) >= 5:
                        return candles
        except Exception:
            pass
            
        return []

    def get_bulk_market_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetches bulk market metrics for all IDX instruments in a single network query.
        Uses EODHD bulk EOD endpoint: /eod-bulk-last-day/JK?fmt=json
        """
        now = datetime.datetime.now()
        if self._bulk_cache and self._bulk_cache_time and (now - self._bulk_cache_time).total_seconds() < 300:
            return self._bulk_cache
            
        url = f"{self.BASE_URL}/eod-bulk-last-day/JK?fmt=json&api_token={self.api_key}"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    bulk_res = {}
                    for item in data:
                        code = item.get("code")
                        if code:
                            clean = code.replace(".JK", "").upper()
                            bulk_res[clean] = {
                                "ticker": clean,
                                "name": clean,
                                "current_price": float(item.get("adjusted_close") or item.get("close") or 0.0),
                                "previous_close": float(item.get("previousClose") or item.get("open") or 0.0),
                                "volume": int(float(item.get("volume") or 0)),
                                "market_cap": float(item.get("market_capitalization") or 0.0)
                            }
                    self._bulk_cache = bulk_res
                    self._bulk_cache_time = now
                    return bulk_res
        except Exception:
            pass
            
        return super().get_bulk_market_data()

    def list_all_tickers(self) -> List[str]:
        """
        Fetches the real list of common-stock symbols on the IDX (.JK exchange) from EODHD.
        Returns an empty list when the live source is unavailable (no fabricated symbols).
        """
        if self._symbol_cache is not None:
            return self._symbol_cache

        url = f"{self.BASE_URL}/exchange-symbol-list/JK?fmt=json&api_token={self.api_key}"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    symbols = []
                    for item in data:
                        code = item.get("Code")
                        sec_type = (item.get("Type") or "").lower()
                        if code and (not sec_type or "common" in sec_type or "stock" in sec_type):
                            symbols.append(code.upper())
                    if symbols:
                        self._symbol_cache = symbols
                        return symbols
        except Exception:
            pass

        return []

    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        """
        Fetches REAL shareholder / ownership composition from the EODHD /fundamentals
        SharesStats and Holders blocks. Returns None when no real data is available.
        No ownership figures are fabricated; unavailable fields stay None/empty.
        """
        clean_ticker = ticker.upper().replace(".JK", "").strip()
        data = self._fetch_fundamentals_raw(clean_ticker)
        if not data:
            return None

        general = data.get("General", {}) or {}
        shares_stats = data.get("SharesStats", {}) or {}
        holders = data.get("Holders", {}) or {}

        name = general.get("Name") or f"{clean_ticker} Tbk"

        # --- Share structure statistics ---
        stats_model = None
        so = shares_stats.get("SharesOutstanding")
        sf = shares_stats.get("SharesFloat")
        pct_insiders = shares_stats.get("PercentInsiders")
        pct_institutions = shares_stats.get("PercentInstitutions")
        shares_short = shares_stats.get("SharesShort")

        float_pct = None
        if so and sf:
            try:
                float_pct = round(float(sf) / float(so) * 100, 2)
            except (ValueError, ZeroDivisionError):
                float_pct = None

        if any(v is not None for v in (so, sf, pct_insiders, pct_institutions, shares_short)):
            stats_model = SharesStatistics(
                shares_outstanding=self._to_float_or_none(so),
                shares_float=self._to_float_or_none(sf),
                float_percentage=float_pct,
                percent_insiders=self._to_float_or_none(pct_insiders),
                percent_institutions=self._to_float_or_none(pct_institutions),
                shares_short=self._to_float_or_none(shares_short),
            )

        # --- Detailed holders (Institutions & Funds) ---
        institutional_holders = self._parse_holder_block(holders.get("Institutions", {}), "Institution")
        fund_holders = self._parse_holder_block(holders.get("Funds", {}), "Fund")

        if not any([stats_model, institutional_holders, fund_holders]):
            # Nothing real to report.
            return None

        insider_pct = self._to_float_or_none(pct_insiders)
        institution_pct = self._to_float_or_none(pct_institutions)
        public_float_pct = float_pct

        notes: List[str] = []
        if not institutional_holders and not fund_holders:
            notes.append("Detailed holder list not provided by source; only aggregate share statistics available.")

        return OwnershipBreakdown(
            ticker=clean_ticker,
            name=name,
            source="EODHD",
            shares_statistics=stats_model,
            public_float_pct=public_float_pct,
            insider_pct=insider_pct,
            institution_pct=institution_pct,
            government_pct=None,
            major_shareholders=[],
            institutional_holders=institutional_holders,
            fund_holders=fund_holders,
            sid_statistics=None,
            is_real_data=True,
            notes=notes,
        )

    def _parse_holder_block(self, block: Any, category: str) -> List[ShareholderEntry]:
        """Parses an EODHD Holders sub-block (dict keyed by index) into ShareholderEntry list."""
        entries: List[ShareholderEntry] = []
        if not isinstance(block, dict):
            return entries
        for _, holder in block.items():
            if not isinstance(holder, dict):
                continue
            hname = holder.get("name") or holder.get("Name")
            if not hname:
                continue
            # EODHD reports totalShares as a percentage of outstanding (e.g. 5.23 == 5.23%)
            pct = self._to_float_or_none(holder.get("totalShares"))
            shares = self._to_float_or_none(holder.get("currentShares"))
            entries.append(ShareholderEntry(
                name=str(hname),
                category=category,
                shares=shares,
                percentage=pct,
                is_controlling=bool(pct is not None and pct > 50.0),
                filing_date=holder.get("date") or holder.get("Date"),
            ))
        return entries

    @staticmethod
    def _to_float_or_none(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def search_tickers(self, query: str) -> List[RawKeyStats]:
        q = query.upper().strip()
        results = []
        for t in self.list_all_tickers():
            if q in t:
                stats = self.get_keystats(t)
                if stats:
                    results.append(stats)
        return results
