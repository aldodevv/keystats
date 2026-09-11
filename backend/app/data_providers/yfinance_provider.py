"""
Yahoo Finance data provider for the Indonesian Stock Exchange (IDX / BEI).

This is the default **free, public, no-API-key** data source for BRIGHTS. It uses the
open-source `yfinance` library to read the same publicly available data shown on
finance.yahoo.com for IDX tickers (suffix `.JK`, e.g. BBRI.JK, ASII.JK).

What it provides for IDX emitens:
  - Live / EOD price, previous close, day change %, shares outstanding, market cap.
  - Multi-year fundamentals (income statement, balance sheet, cash flow) in IDR.
  - Corporate-action adjusted historical OHLCV candles.
  - Ownership / shareholder composition (institutional & fund holders, insider/institution %)
    where Yahoo exposes it.

Real-data-only: every value is read from the live Yahoo response. Missing datapoints stay
None / 0.0 and are never fabricated. When the ticker or the whole source is unreachable the
methods return None / empty lists so the orchestrator can fall through or fail loudly.

yfinance is free and requires no key, so this provider is always "configured".
"""

import datetime
from typing import Optional, List, Dict, Any

try:
    import yfinance as yf
except Exception:  # pragma: no cover - import guard
    yf = None

from app.data_providers.base import BaseDataProvider
from app.data_providers.idx_universe import get_idx_universe
from app.models.keystats import RawKeyStats, FinancialPeriod, BankSpecificMetrics
from app.models.chart import CandleDataPoint
from app.models.xbrl import XBRLEntryPoint
from app.models.financial_matrix import StockbitFinancialMatrix, QuarterlyDataPoint
from app.models.ownership import (
    OwnershipBreakdown,
    ShareholderEntry,
    SharesStatistics,
)


class YFinanceProvider(BaseDataProvider):
    """Free, public IDX data via Yahoo Finance (yfinance). No API key required."""

    def __init__(self) -> None:
        self._ticker_cache: Dict[str, Any] = {}
        self._info_cache: Dict[str, Dict[str, Any]] = {}
        self._symbol_cache: Optional[List[str]] = None

    @property
    def is_configured(self) -> bool:
        # yfinance needs no key; it's usable whenever the library is importable.
        return yf is not None

    # -------------------------------------------------------------
    # Low-level yfinance access (cached per clean ticker)
    # -------------------------------------------------------------
    def _yf_ticker(self, clean_ticker: str):
        if yf is None:
            return None
        if clean_ticker not in self._ticker_cache:
            self._ticker_cache[clean_ticker] = yf.Ticker(f"{clean_ticker}.JK")
        return self._ticker_cache[clean_ticker]

    def _info(self, clean_ticker: str) -> Dict[str, Any]:
        if clean_ticker in self._info_cache:
            return self._info_cache[clean_ticker]
        info: Dict[str, Any] = {}
        tk = self._yf_ticker(clean_ticker)
        if tk is not None:
            try:
                # get_info() is the resilient accessor; fall back to .info if needed.
                info = tk.get_info() or {}
            except Exception:
                try:
                    info = dict(tk.info or {})
                except Exception:
                    info = {}
        self._info_cache[clean_ticker] = info
        return info

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------
    @staticmethod
    def _f(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            fv = float(value)
            # Guard against NaN.
            return fv if fv == fv else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _fo(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            fv = float(value)
            return fv if fv == fv else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _row_get(df, row_names: List[str], col) -> Optional[float]:
        """Reads a value from a yfinance statement DataFrame by trying several row labels."""
        if df is None:
            return None
        try:
            index = list(df.index)
        except Exception:
            return None
        for name in row_names:
            if name in index:
                try:
                    val = df.loc[name, col]
                except Exception:
                    continue
                fv = YFinanceProvider._fo(val)
                if fv is not None:
                    return fv
        return None

    # -------------------------------------------------------------
    # BaseDataProvider implementation
    # -------------------------------------------------------------
    def get_keystats(
        self,
        ticker: str,
        override_price: Optional[float] = None,
        force_live: bool = False,
    ) -> Optional[RawKeyStats]:
        if yf is None:
            return None
        clean = ticker.upper().replace(".JK", "").strip()
        tk = self._yf_ticker(clean)
        if tk is None:
            return None

        info = self._info(clean)
        if not info:
            return None

        name = info.get("longName") or info.get("shortName") or f"{clean} Tbk"
        sector = info.get("sector") or "General"
        industry = info.get("industry") or "General"

        price = self._f(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("regularMarketPreviousClose")
            or info.get("previousClose")
        )
        if override_price and override_price > 0:
            price = float(override_price)

        prev_close = self._fo(info.get("regularMarketPreviousClose") or info.get("previousClose"))
        change_pct = self._fo(info.get("regularMarketChangePercent"))
        if change_pct is None and prev_close and prev_close > 0 and price > 0:
            change_pct = round((price - prev_close) / prev_close * 100, 2)

        shares = self._f(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))
        market_cap = self._f(info.get("marketCap"))
        if market_cap <= 0 and price > 0 and shares > 0:
            market_cap = price * shares
        if shares <= 0 and market_cap > 0 and price > 0:
            shares = market_cap / price

        is_bank = "bank" in str(sector).lower() or "bank" in str(industry).lower() or \
            "financ" in str(sector).lower()
        entry_point = XBRLEntryPoint.FINANCIAL_BANKING if is_bank else XBRLEntryPoint.GENERAL_INDUSTRY

        # Fetch statements once and reuse.
        income_a = self._safe_stmt(tk, "income_stmt")
        balance_a = self._safe_stmt(tk, "balance_sheet")
        cashflow_a = self._safe_stmt(tk, "cashflow")
        income_q = self._safe_stmt(tk, "quarterly_income_stmt")

        current_period, previous_period, historical = self._build_periods(
            income_a, balance_a, cashflow_a, shares, entry_point
        )
        if current_period is None:
            # Fall back to a minimal period built from `info` TTM figures if available.
            current_period = self._period_from_info(info, shares, entry_point)
        if current_period is None:
            return None

        matrix = self._build_matrix(income_q, shares)

        bank_metrics = None
        if is_bank:
            bank_metrics = self._build_bank_metrics(info, current_period)

        return RawKeyStats(
            ticker=clean,
            name=str(name),
            sector=str(sector),
            industry=str(industry),
            xbrl_entry_point=entry_point,
            current_price=price,
            previous_close=prev_close,
            price_change_pct=change_pct or 0.0,
            is_realtime=bool(info.get("regularMarketPrice")),
            last_updated_time=datetime.datetime.now().isoformat(),
            shares_outstanding=shares if shares > 0 else 1.0,
            market_cap=market_cap,
            current_period=current_period,
            previous_period=previous_period,
            historical_periods=historical,
            financial_matrix=matrix,
            dps=self._f(info.get("dividendRate") or info.get("lastDividendValue")),
            beta=self._f(info.get("beta")) or 1.0,
            bank_metrics=bank_metrics,
        )

    @staticmethod
    def _safe_stmt(tk, attr: str):
        """Reads a yfinance financial-statement DataFrame safely."""
        try:
            df = getattr(tk, attr)
        except Exception:
            return None
        try:
            if df is None or getattr(df, "empty", True):
                return None
        except Exception:
            return None
        return df

    def _build_periods(self, income, balance, cashflow, shares: float, entry_point: XBRLEntryPoint):
        """Builds FinancialPeriod objects from yfinance annual statement DataFrames."""
        if income is None:
            return None, None, []
        try:
            columns = list(income.columns)
        except Exception:
            return None, None, []
        if not columns:
            return None, None, []

        # Columns are pandas Timestamps, newest first.
        def _col_year(col) -> int:
            try:
                return int(str(col)[:4])
            except Exception:
                return datetime.datetime.now().year

        # Sort columns newest → oldest by year.
        columns = sorted(columns, key=_col_year, reverse=True)

        periods: List[FinancialPeriod] = []
        for col in columns[:6]:
            p = self._col_to_period(col, income, balance, cashflow, shares, entry_point)
            if p:
                periods.append(p)

        if not periods:
            return None, None, []

        current = periods[0]
        previous = periods[1] if len(periods) > 1 else None
        historical = periods[1:6]
        return current, previous, historical

    def _col_to_period(self, col, income, balance, cashflow, shares: float, entry_point) -> Optional[FinancialPeriod]:
        year = int(str(col)[:4]) if str(col)[:4].isdigit() else datetime.datetime.now().year
        g = self._row_get

        revenue = g(income, ["Total Revenue", "Operating Revenue", "TotalRevenue"], col) or 0.0
        gross_profit = g(income, ["Gross Profit", "GrossProfit"], col) or 0.0
        operating = g(income, ["Operating Income", "OperatingIncome", "Total Operating Income As Reported"], col) or 0.0
        ebit = g(income, ["EBIT", "Ebit"], col) or operating
        ebitda = g(income, ["EBITDA", "Normalized EBITDA"], col) or 0.0
        net_income = g(income, ["Net Income", "Net Income Common Stockholders", "NetIncome"], col) or 0.0
        eps = g(income, ["Diluted EPS", "Basic EPS"], col)
        if eps is None or eps == 0.0:
            eps = net_income / shares if shares > 0 else 0.0

        total_assets = g(balance, ["Total Assets", "TotalAssets"], col) or 0.0
        current_assets = g(balance, ["Current Assets", "Total Current Assets"], col) or 0.0
        cash = g(balance, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"], col) or 0.0
        inventory = g(balance, ["Inventory"], col) or 0.0
        receivables = g(balance, ["Receivables", "Accounts Receivable", "Net Receivables"], col) or 0.0
        total_liab = g(balance, ["Total Liabilities Net Minority Interest", "Total Liab", "Total Liabilities"], col) or 0.0
        current_liab = g(balance, ["Current Liabilities", "Total Current Liabilities"], col) or 0.0
        total_debt = g(balance, ["Total Debt", "TotalDebt"], col) or 0.0
        st_debt = g(balance, ["Current Debt", "Short Term Debt", "Current Debt And Capital Lease Obligation"], col) or 0.0
        lt_debt = g(balance, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"], col) or 0.0
        if total_debt == 0.0:
            total_debt = st_debt + lt_debt
        total_equity = g(balance, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"], col) or 0.0
        retained = g(balance, ["Retained Earnings"], col) or 0.0

        cfo = g(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities", "Cash Flow From Continuing Operating Activities"], col) or 0.0
        capex = g(cashflow, ["Capital Expenditure", "Capital Expenditures"], col) or 0.0
        fcf = g(cashflow, ["Free Cash Flow"], col)
        if fcf is None:
            fcf = cfo - abs(capex) if cfo != 0.0 else 0.0
        div_paid = g(cashflow, ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividends Paid"], col) or 0.0

        # Bank-specific (Yahoo exposes some of these for financials).
        interest_income = g(income, ["Interest Income", "Total Money Market Investments"], col) or 0.0
        net_interest_income = g(income, ["Net Interest Income"], col) or 0.0

        return FinancialPeriod(
            year=year,
            filing_date=str(col)[:10],
            xbrl_entry_point=entry_point,
            revenue=revenue,
            gross_profit=gross_profit,
            operating_profit=operating,
            ebit=ebit,
            ebitda=ebitda,
            net_income=net_income,
            eps=eps,
            total_assets=total_assets,
            current_assets=current_assets,
            cash_and_equivalents=cash,
            inventory=inventory,
            receivables=receivables,
            total_liabilities=total_liab,
            current_liabilities=current_liab,
            total_debt=total_debt,
            short_term_debt=st_debt,
            long_term_debt=lt_debt,
            total_equity=total_equity,
            retained_earnings=retained,
            cfo=cfo,
            capex=capex,
            fcf=fcf,
            dividends_paid=abs(div_paid),
            shares_outstanding=shares,
            interest_income=interest_income,
            net_interest_income=net_interest_income,
        )

    def _period_from_info(self, info: Dict[str, Any], shares: float, entry_point) -> Optional[FinancialPeriod]:
        """Last-resort period from `info` TTM figures when statements are unavailable."""
        revenue = self._f(info.get("totalRevenue"))
        net_income = self._f(info.get("netIncomeToCommon"))
        if revenue <= 0 and net_income == 0.0:
            return None
        eps = self._f(info.get("trailingEps")) or (net_income / shares if shares > 0 else 0.0)
        return FinancialPeriod(
            year=datetime.datetime.now().year,
            xbrl_entry_point=entry_point,
            revenue=revenue,
            net_income=net_income,
            eps=eps,
            total_equity=self._f(info.get("totalStockholderEquity")),
            total_debt=self._f(info.get("totalDebt")),
            cash_and_equivalents=self._f(info.get("totalCash")),
            shares_outstanding=shares,
        )

    def _build_matrix(self, income_q, shares: float) -> Optional[StockbitFinancialMatrix]:
        """Builds a per-year quarterly matrix from yfinance quarterly income statement."""
        if income_q is None:
            return None
        try:
            columns = list(income_q.columns)
        except Exception:
            return None
        if not columns:
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

        for col in columns:
            col_str = str(col)
            if len(col_str) < 7 or not col_str[:4].isdigit():
                continue
            year = col_str[:4]
            try:
                month = int(col_str[5:7])
            except ValueError:
                continue
            years_seen.add(int(year))
            slot = _q_slot(month)

            rev = self._row_get(income_q, ["Total Revenue", "Operating Revenue"], col)
            ni = self._row_get(income_q, ["Net Income", "Net Income Common Stockholders"], col)

            net_income_matrix.setdefault(year, QuarterlyDataPoint())
            revenue_matrix.setdefault(year, QuarterlyDataPoint())
            eps_matrix.setdefault(year, QuarterlyDataPoint())

            if ni is not None:
                setattr(net_income_matrix[year], slot, ni)
                if shares > 0:
                    setattr(eps_matrix[year], slot, round(ni / shares, 2))
            if rev is not None:
                setattr(revenue_matrix[year], slot, rev)

        if not years_seen:
            return None

        return StockbitFinancialMatrix(
            years=sorted(years_seen, reverse=True),
            currency="IDR",
            net_income_matrix=net_income_matrix,
            eps_matrix=eps_matrix,
            revenue_matrix=revenue_matrix,
        )

    def _build_bank_metrics(self, info: Dict[str, Any], curr: FinancialPeriod) -> Optional[BankSpecificMetrics]:
        """
        Derives NIM/LDR from real reported line items when present. Yahoo does not expose
        OJK-specific ratios (CAR, NPL, BOPO, CASA, cost-of-credit) for IDX banks, so those
        remain None rather than fabricated.
        """
        nim = None
        if curr.net_interest_income > 0 and curr.earning_assets > 0:
            nim = round(curr.net_interest_income / curr.earning_assets * 100, 2)

        ldr = None
        if curr.total_loans > 0 and curr.deposits_dpk > 0:
            ldr = round(curr.total_loans / curr.deposits_dpk * 100, 2)

        if not any([nim, ldr, curr.net_interest_income > 0, curr.total_loans > 0]):
            return None

        return BankSpecificMetrics(
            car=None,
            npl_gross=None,
            npl_net=None,
            nim=nim,
            bopo=None,
            ldr=ldr,
            casa=None,
            cost_of_credit=None,
            earning_assets=curr.earning_assets or None,
            total_loans=curr.total_loans or None,
            deposits_dpk=curr.deposits_dpk or None,
        )

    def get_historical_ohlcv(self, ticker: str, timeframe: str = "1y") -> List[CandleDataPoint]:
        """Corporate-action adjusted daily OHLCV from Yahoo Finance."""
        if yf is None:
            return []
        clean = ticker.upper().replace(".JK", "").strip()
        tk = self._yf_ticker(clean)
        if tk is None:
            return []

        period_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y", "5y": "5y"}
        period = period_map.get(timeframe.lower(), "1y")

        try:
            df = tk.history(period=period, interval="1d", auto_adjust=True)
        except Exception:
            return []
        if df is None or getattr(df, "empty", True):
            return []

        candles: List[CandleDataPoint] = []
        try:
            for idx, row in df.iterrows():
                close = self._f(row.get("Close"))
                if close <= 0:
                    continue
                o = self._f(row.get("Open")) or close
                h = self._f(row.get("High")) or close
                l = self._f(row.get("Low")) or close
                v = int(self._f(row.get("Volume")))
                candles.append(CandleDataPoint(
                    time=str(idx)[:10],
                    open=round(o, 2),
                    high=round(h, 2),
                    low=round(l, 2),
                    close=round(close, 2),
                    volume=v,
                ))
        except Exception:
            return candles
        return candles

    def list_all_tickers(self) -> List[str]:
        """
        Yahoo Finance has no free "list all IDX symbols" endpoint, so we return a curated
        universe of real IDX ticker CODES (LQ45/IDX80 + other liquid emitens). These are
        public identifiers only — each emiten's actual figures are still fetched live from
        Yahoo. Override/extend via the IDX_TICKER_UNIVERSE env var.
        """
        if self._symbol_cache is None:
            self._symbol_cache = get_idx_universe()
        return self._symbol_cache

    def search_tickers(self, query: str) -> List[RawKeyStats]:
        """
        Search the IDX universe by ticker code (and, best-effort, by company name).

        1. Direct code match resolves immediately (e.g. "PTBA").
        2. Otherwise, match the query as a substring of universe codes.
        Returns live stats for each match (capped for responsiveness).
        """
        q = query.upper().replace(".JK", "").strip()
        if not q:
            return []

        universe = self.list_all_tickers()

        # Exact code hit first.
        ordered: List[str] = []
        if q in universe:
            ordered.append(q)
        # Then substring code matches (prefix-priority).
        for code in universe:
            if code == q:
                continue
            if code.startswith(q) or q in code:
                ordered.append(code)

        # If the query isn't in our universe at all, still try to resolve it directly
        # (user may search a valid IDX code we didn't bundle).
        if not ordered:
            ordered = [q]

        results: List[RawKeyStats] = []
        for code in ordered[:10]:
            stats = self.get_keystats(code)
            if stats:
                results.append(stats)
        return results

    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        """Ownership composition from Yahoo Finance holders data, where available."""
        if yf is None:
            return None
        clean = ticker.upper().replace(".JK", "").strip()
        tk = self._yf_ticker(clean)
        if tk is None:
            return None

        info = self._info(clean)
        name = info.get("longName") or info.get("shortName") or f"{clean} Tbk"

        pct_insiders = self._fo(info.get("heldPercentInsiders"))
        pct_institutions = self._fo(info.get("heldPercentInstitutions"))
        # Yahoo reports these as fractions (0.42 == 42%).
        if pct_insiders is not None and pct_insiders <= 1.5:
            pct_insiders = round(pct_insiders * 100, 2)
        if pct_institutions is not None and pct_institutions <= 1.5:
            pct_institutions = round(pct_institutions * 100, 2)

        shares_out = self._fo(info.get("sharesOutstanding"))
        float_shares = self._fo(info.get("floatShares"))
        float_pct = None
        if shares_out and float_shares:
            float_pct = round(float_shares / shares_out * 100, 2)

        stats_model = None
        if any(v is not None for v in (shares_out, float_shares, pct_insiders, pct_institutions)):
            stats_model = SharesStatistics(
                shares_outstanding=shares_out,
                shares_float=float_shares,
                float_percentage=float_pct,
                percent_insiders=pct_insiders,
                percent_institutions=pct_institutions,
            )

        institutional_holders = self._parse_holders_df(
            self._safe_holders(tk, "institutional_holders"), "Institution"
        )
        fund_holders = self._parse_holders_df(
            self._safe_holders(tk, "mutualfund_holders"), "Fund"
        )

        if not any([stats_model, institutional_holders, fund_holders]):
            return None

        notes: List[str] = []
        if not institutional_holders and not fund_holders:
            notes.append("Detailed holder list not provided by Yahoo Finance for this ticker; only aggregate share statistics available.")

        return OwnershipBreakdown(
            ticker=clean,
            name=str(name),
            source="Yahoo Finance",
            shares_statistics=stats_model,
            public_float_pct=float_pct,
            insider_pct=pct_insiders,
            institution_pct=pct_institutions,
            government_pct=None,
            major_shareholders=[],
            institutional_holders=institutional_holders,
            fund_holders=fund_holders,
            sid_statistics=None,
            is_real_data=True,
            notes=notes,
        )

    @staticmethod
    def _safe_holders(tk, attr: str):
        try:
            df = getattr(tk, attr)
        except Exception:
            return None
        try:
            if df is None or getattr(df, "empty", True):
                return None
        except Exception:
            return None
        return df

    def _parse_holders_df(self, df, category: str) -> List[ShareholderEntry]:
        entries: List[ShareholderEntry] = []
        if df is None:
            return entries
        try:
            records = df.to_dict("records")
        except Exception:
            return entries
        for rec in records:
            name = rec.get("Holder") or rec.get("holder")
            if not name:
                continue
            pct = self._fo(rec.get("pctHeld") or rec.get("% Out"))
            if pct is not None and pct <= 1.5:
                pct = round(pct * 100, 2)
            shares = self._fo(rec.get("Shares") or rec.get("shares"))
            date_reported = rec.get("Date Reported") or rec.get("dateReported")
            entries.append(ShareholderEntry(
                name=str(name),
                category=category,
                shares=shares,
                percentage=pct,
                is_controlling=bool(pct is not None and pct > 50.0),
                filing_date=str(date_reported)[:10] if date_reported else None,
            ))
        return entries
