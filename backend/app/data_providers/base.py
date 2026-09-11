"""
Base Data Provider Interface for IDX Keystats and Financial Statements.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.models.keystats import RawKeyStats
from app.models.chart import CandleDataPoint
from app.models.ownership import OwnershipBreakdown


class BaseDataProvider(ABC):
    @abstractmethod
    def get_keystats(
        self,
        ticker: str,
        override_price: Optional[float] = None,
        force_live: bool = False
    ) -> Optional[RawKeyStats]:
        """Fetches raw keystats and XBRL financial statements for a given ticker."""
        pass
        
    @abstractmethod
    def list_all_tickers(self) -> List[str]:
        """Returns all available IDX tickers."""
        pass
        
    @abstractmethod
    def search_tickers(self, query: str) -> List[RawKeyStats]:
        """Searches tickers by code or name."""
        pass

    @abstractmethod
    def get_historical_ohlcv(self, ticker: str, timeframe: str = "1y") -> List[CandleDataPoint]:
        """Fetches corporate-action adjusted historical daily OHLCV candlestick data."""
        pass

    @abstractmethod
    def get_shareholders(self, ticker: str) -> Optional[OwnershipBreakdown]:
        """
        Fetches real shareholder / stakeholder ownership composition for a ticker:
        major shareholders, ownership percentages, free float, institutional/fund holders,
        and (when available) KSEI SID retail-participation statistics.

        Returns None when no real data source can supply the data. Implementations MUST NOT
        fabricate ownership figures.
        """
        pass

    def get_bulk_market_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetches bulk market data (prices, market cap, key metrics) for all IDX stocks in a single round-trip.
        Default implementation provides compatibility by querying tickers.
        """
        result = {}
        for ticker in self.list_all_tickers():
            stats = self.get_keystats(ticker)
            if stats:
                result[ticker] = {
                    "ticker": stats.ticker,
                    "name": stats.name,
                    "sector": stats.sector,
                    "current_price": stats.current_price,
                    "market_cap": stats.market_cap,
                    "shares_outstanding": stats.shares_outstanding
                }
        return result

