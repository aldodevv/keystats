"""
Emiten Service: Coordinates data fetching and analytical scoring for single emitens.
Uses InstitutionalDataProvider as primary data source.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List
from app.data_providers.base import BaseDataProvider
from app.data_providers.institutional_provider import InstitutionalDataProvider
from app.engines.scoring_engine import ScoringEngine
from app.models.score import EmitenAnalysisReport
from app.models.keystats import RawKeyStats
from app.models.ownership import OwnershipBreakdown
from app.services.ksei_service import KSEIStatisticsService


class EmitenService:
    # Cache full analysis reports briefly so market summary / screener don't re-fetch the
    # same emiten repeatedly across endpoints. Prices update intraday; 5 min is a good
    # balance for a delayed (~15 min) free feed.
    _report_cache: dict = {}
    _report_cache_ttl_seconds = 300
    # How many emitens to analyze concurrently for market-wide features. yfinance calls
    # are I/O-bound, so a higher count meaningfully cuts full-universe cold-load time.
    _max_workers = 16

    def __init__(self, provider: Optional[BaseDataProvider] = None):
        self.provider = provider or InstitutionalDataProvider()

    def analyze_single_emiten(
        self,
        ticker: str,
        override_price: Optional[float] = None,
        force_live: bool = False,
        include_ownership: bool = True,
    ) -> Optional[EmitenAnalysisReport]:
        raw = self.provider.get_keystats(ticker, override_price=override_price, force_live=force_live)
        if not raw:
            return None
        report = ScoringEngine.analyze_emiten(raw)

        # Attach real shareholder/ownership composition (best-effort; never blocks analysis).
        # Skipped for bulk/market-wide passes to avoid an extra network round-trip per emiten.
        if include_ownership:
            try:
                report.ownership = self.get_shareholders(ticker)
            except Exception:
                report.ownership = None

        return report

    def _cached_report(self, ticker: str) -> Optional[EmitenAnalysisReport]:
        """Returns a cached lightweight report (no ownership) for market-wide features."""
        clean = ticker.upper().replace(".JK", "").strip()
        now = time.time()
        cached = self._report_cache.get(clean)
        if cached and (now - cached[0]) < self._report_cache_ttl_seconds:
            return cached[1]
        try:
            report = self.analyze_single_emiten(clean, include_ownership=False)
        except Exception:
            report = None
        # Cache both hits and misses (None) to avoid hammering a failing ticker repeatedly.
        self._report_cache[clean] = (now, report)
        return report

    def analyze_many(self, tickers: List[str]) -> List[EmitenAnalysisReport]:
        """
        Analyzes many emitens concurrently (cached), returning only those that resolve to
        real data. Used by market summary, screener, and price-tier recommendations so a
        full IDX-universe pass returns in seconds instead of minutes.
        """
        reports: List[EmitenAnalysisReport] = []
        if not tickers:
            return reports
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(self._cached_report, t): t for t in tickers}
            for fut in as_completed(futures):
                try:
                    rep = fut.result()
                except Exception:
                    rep = None
                if rep:
                    reports.append(rep)
        return reports

    def search_emitens(self, query: str) -> List[RawKeyStats]:
        return self.provider.search_tickers(query)

    def list_all_available_tickers(self) -> List[str]:
        return self.provider.list_all_tickers()

    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        """
        Retrieves real shareholder / stakeholder ownership composition for a ticker,
        enriched (when configured) with KSEI SID retail-participation statistics.
        Returns None when no real ownership data is available.
        """
        ownership = self.provider.get_shareholders(ticker)
        if ownership is None:
            return None

        sid = KSEIStatisticsService.get_market_sid()
        if sid is not None:
            ownership.sid_statistics = sid
        return ownership
