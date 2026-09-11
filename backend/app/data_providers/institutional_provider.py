"""
Primary Data Orchestrator for BRIGHTS — BRI Stock Intelligence (IDX / BEI).

Real-data-only. Chains legitimate data sources and returns the first that supplies real
data. There is NO synthetic seed dataset and NO fabricated fallback: when no source can
supply data, the provider fails loudly rather than inventing numbers.

Source precedence (configurable via DATA_SOURCE_PRIORITY, comma-separated):
  1. "yfinance" — Yahoo Finance via the free open-source `yfinance` library. **Default,
                  free, public, no API key.** IDX tickers (.JK): prices, adjusted OHLCV,
                  multi-year fundamentals (IDR), and holder composition where exposed.
  2. "sectors"  — Sectors.app (Supertype). Licensed IDX/KSEI fundamentals & shareholders.
                  Optional; only active when SECTORS_API_KEY is set.
  3. "eodhd"    — EODHD. Global fundamentals + realtime prices. Optional; only active when
                  a real EODHD_API_KEY is set.

Default priority: "yfinance,sectors,eodhd". The two licensed sources are used only if the
operator has configured their keys; otherwise BRIGHTS runs entirely on free Yahoo data.
"""

import os
from typing import Optional, List, Dict, Any

from app.data_providers.base import BaseDataProvider
from app.data_providers.yfinance_provider import YFinanceProvider
from app.data_providers.sectors_provider import SectorsProvider
from app.data_providers.eodhd_provider import EODHDProvider
from app.models.keystats import RawKeyStats
from app.models.chart import CandleDataPoint
from app.models.ownership import OwnershipBreakdown


class DataSourceNotConfiguredError(RuntimeError):
    """Raised when no real market-data source is configured/reachable."""


class InstitutionalDataProvider(BaseDataProvider):
    """
    Orchestrates real IDX data sources in configurable priority order.
    Uses free Yahoo Finance by default; licensed sources (Sectors.app, EODHD) are optional.
    """

    def __init__(
        self,
        sectors_api_key: Optional[str] = None,
        eodhd_api_key: Optional[str] = None,
    ):
        self.yfinance = YFinanceProvider()
        self.sectors = SectorsProvider(api_key=sectors_api_key)
        self.eodhd = EODHDProvider(api_key=eodhd_api_key)

        priority = os.getenv("DATA_SOURCE_PRIORITY", "yfinance,sectors,eodhd")
        self._priority = [p.strip().lower() for p in priority.split(",") if p.strip()]

    # -------------------------------------------------------------
    # Source resolution
    # -------------------------------------------------------------
    def _eodhd_ready(self) -> bool:
        return bool(self.eodhd.api_key) and self.eodhd.api_key != "demo"

    def _configured_sources(self) -> List[BaseDataProvider]:
        """Returns configured providers in priority order (usable sources only)."""
        available = {
            "yfinance": self.yfinance if self.yfinance.is_configured else None,
            "sectors": self.sectors if self.sectors.is_configured else None,
            "eodhd": self.eodhd if self._eodhd_ready() else None,
        }
        ordered = [available[name] for name in self._priority if available.get(name)]
        # Include any configured source not named in priority (defensive).
        for name, prov in available.items():
            if prov is not None and prov not in ordered:
                ordered.append(prov)
        return ordered

    @property
    def is_configured(self) -> bool:
        return len(self._configured_sources()) > 0

    def _require_source(self) -> List[BaseDataProvider]:
        sources = self._configured_sources()
        if not sources:
            raise DataSourceNotConfiguredError(
                "No real market-data source available. The default free source is Yahoo "
                "Finance (install the 'yfinance' package). Optionally set SECTORS_API_KEY "
                "(Sectors.app) and/or EODHD_API_KEY for licensed data. "
                "Mock/synthetic data has been permanently removed from this platform."
            )
        return sources

    # -------------------------------------------------------------
    # BaseDataProvider implementation (first source that answers wins)
    # -------------------------------------------------------------
    def get_keystats(
        self,
        ticker: str,
        override_price: Optional[float] = None,
        force_live: bool = False,
    ) -> Optional[RawKeyStats]:
        clean = ticker.upper().replace(".JK", "").strip()
        for source in self._require_source():
            try:
                data = source.get_keystats(clean, override_price=override_price, force_live=force_live)
            except Exception:
                data = None
            if data and data.current_period and data.current_period.revenue > 0:
                return data
        return None

    def list_all_tickers(self) -> List[str]:
        for source in self._require_source():
            try:
                tickers = source.list_all_tickers()
            except Exception:
                tickers = []
            if tickers:
                return tickers
        return []

    def search_tickers(self, query: str) -> List[RawKeyStats]:
        for source in self._require_source():
            try:
                results = source.search_tickers(query)
            except Exception:
                results = []
            if results:
                return results
        return []

    def get_historical_ohlcv(self, ticker: str, timeframe: str = "1y") -> List[CandleDataPoint]:
        clean = ticker.upper().replace(".JK", "").strip()
        for source in self._require_source():
            try:
                candles = source.get_historical_ohlcv(clean, timeframe)
            except Exception:
                candles = []
            if candles and len(candles) >= 5:
                return candles
        return []

    def get_bulk_market_data(self) -> Dict[str, Dict[str, Any]]:
        for source in self._require_source():
            try:
                bulk = source.get_bulk_market_data()
            except Exception:
                bulk = None
            if bulk and len(bulk) > 0:
                return bulk
        return {}

    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        clean = ticker.upper().replace(".JK", "").strip()
        for source in self._require_source():
            try:
                ownership = source.get_shareholders(clean)
            except Exception:
                ownership = None
            if ownership:
                return ownership
        return None
