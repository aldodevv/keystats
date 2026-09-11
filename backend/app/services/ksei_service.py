"""
KSEI Statistics Service.

Provides Indonesian capital-market Single Investor Identification (SID) statistics,
the authoritative measure of registered investor participation published by KSEI
(Kustodian Sentral Efek Indonesia).

KSEI does not expose a stable free public REST API for these statistics. To keep this
platform strictly real-data-only, SID figures are fetched from a JSON endpoint that the
operator explicitly configures via the KSEI_STATISTICS_URL environment variable
(for example, an internal proxy that mirrors KSEI's published statistics). When no such
source is configured, the service returns None instead of fabricating SID counts.

Expected JSON shape from KSEI_STATISTICS_URL (flexible key matching applied):
    {
      "total_sid": 14200000,
      "equity_sid": 6100000,
      "as_of_date": "2026-07-31"
    }
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime

import requests

from app.models.ownership import SIDStatistics


class KSEIStatisticsService:
    _cache: Optional[SIDStatistics] = None
    _cache_time: Optional[datetime] = None
    _CACHE_TTL_SECONDS = 6 * 60 * 60  # SID stats update at most monthly; cache 6h

    @classmethod
    def get_market_sid(cls) -> Optional[SIDStatistics]:
        """
        Returns market-wide KSEI SID statistics from the configured real source,
        or None when no source is configured / reachable. Never fabricates values.
        """
        url = os.getenv("KSEI_STATISTICS_URL", "").strip()
        if not url:
            return None

        now = datetime.now()
        if (
            cls._cache is not None
            and cls._cache_time is not None
            and (now - cls._cache_time).total_seconds() < cls._CACHE_TTL_SECONDS
        ):
            return cls._cache

        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            sid = cls._parse(data)
            if sid is not None:
                cls._cache = sid
                cls._cache_time = now
            return sid
        except Exception:
            return None

    @staticmethod
    def _parse(data: Any) -> Optional[SIDStatistics]:
        if not isinstance(data, dict):
            return None

        def _pick_int(*keys: str) -> Optional[int]:
            for k in keys:
                if k in data and data[k] not in (None, ""):
                    try:
                        return int(float(data[k]))
                    except (ValueError, TypeError):
                        continue
            return None

        total_sid = _pick_int("total_sid", "totalSID", "total", "sid")
        equity_sid = _pick_int("equity_sid", "equitySID", "equity", "stock_sid")
        as_of = data.get("as_of_date") or data.get("date") or data.get("period")

        if total_sid is None and equity_sid is None:
            return None

        return SIDStatistics(
            total_sid=total_sid,
            equity_sid=equity_sid,
            as_of_date=str(as_of) if as_of else None,
            source="KSEI",
        )
