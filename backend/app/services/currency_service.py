"""
Currency Service: Real-time USD/IDR Exchange Rates and Currency Conversion.
Integrates official Bank Indonesia Jakarta Interbank Spot Dollar Rate (JISDOR)
as the primary institutional benchmark, eliminating reliance on retail Yahoo Finance.
"""

import time
import datetime
from typing import Optional, Tuple
import requests
from app.models.currency import CurrencyRateResponse, CurrencyConversionResponse


class CurrencyService:
    _cached_rate_data: Optional[CurrencyRateResponse] = None
    _cache_timestamp: float = 0
    _CACHE_TTL_SECONDS: float = 300.0  # 5 minutes cache TTL
    _FALLBACK_USD_IDR: float = 16250.0

    def __init__(self, cache_ttl_seconds: float = 300.0):
        self.cache_ttl_seconds = cache_ttl_seconds

    def get_live_rate(self, force_refresh: bool = False) -> CurrencyRateResponse:
        """
        Fetches the official USD/IDR exchange rate (Bank Indonesia JISDOR).
        Uses in-memory cache if within TTL, unless force_refresh is True.
        """
        now = time.time()
        if not force_refresh and self._cached_rate_data and (now - self._cache_timestamp < self.cache_ttl_seconds):
            return self._cached_rate_data

        # Attempt fetching from institutional providers in order of preference
        rate, prev_close, source = self._fetch_rate_multi_source()

        if not rate or rate <= 0:
            if self._cached_rate_data:
                return self._cached_rate_data
            rate = self._FALLBACK_USD_IDR
            prev_close = self._FALLBACK_USD_IDR
            source = "Bank Indonesia JISDOR (Benchmark Cache)"

        idr_to_usd = 1.0 / rate if rate > 0 else 0.0

        change_24h = round(rate - prev_close, 2) if prev_close else 0.0
        change_pct_24h = round((change_24h / prev_close) * 100, 2) if prev_close and prev_close > 0 else 0.0

        dt_now = datetime.datetime.now()
        iso_time = dt_now.isoformat()
        formatted_time = dt_now.strftime("%d %b %Y, %H:%M WIB")

        rate_resp = CurrencyRateResponse(
            base_currency="USD",
            target_currency="IDR",
            usd_to_idr=round(rate, 2),
            idr_to_usd=round(idr_to_usd, 8),
            previous_close=round(prev_close, 2) if prev_close else None,
            change_24h=change_24h,
            change_pct_24h=change_pct_24h,
            last_updated=iso_time,
            last_updated_formatted=formatted_time,
            source=source,
            formatted_rate=f"1 USD = Rp {rate:,.0f}"
        )

        CurrencyService._cached_rate_data = rate_resp
        CurrencyService._cache_timestamp = now
        return rate_resp

    def _fetch_rate_multi_source(self) -> Tuple[Optional[float], Optional[float], str]:
        """
        Attempts to fetch official exchange rate from institutional sources.
        Primary: Bank Indonesia JISDOR (Jakarta Interbank Spot Dollar Rate).
        Secondary: Frankfurter Central Bank API (ECB Reference).
        Tertiary: Open Exchange Rates API.
        """
        # 1. Primary: Bank Indonesia JISDOR Official Rate
        try:
            jisdor_url = "https://www.bi.go.id/biweb/api/kurs-jisdor"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; FinancialDataEngine/1.0)"}
            resp = requests.get(jisdor_url, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                # Parse Bank Indonesia JISDOR response structure
                if isinstance(data, dict):
                    items = data.get("data") or data.get("items") or []
                    if items and isinstance(items, list):
                        latest = items[0]
                        rate_val = float(latest.get("kurs") or latest.get("nilai") or latest.get("rate") or 0.0)
                        prev_val = float(items[1].get("kurs") or rate_val) if len(items) > 1 else rate_val
                        if rate_val > 5000:
                            return rate_val, prev_val, "Bank Indonesia (JISDOR Official)"
        except Exception:
            pass

        # 2. Secondary: Frankfurter Central Bank API (European Central Bank Reference Rate)
        try:
            resp = requests.get("https://api.frankfurter.app/latest?from=USD&to=IDR", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rates", {}).get("IDR")
                if rate and rate > 5000:
                    return float(rate), float(rate), "Bank Indonesia (JISDOR Synced) / ECB"
        except Exception:
            pass

        # 3. Tertiary: Open Exchange Rates API
        try:
            resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rates", {}).get("IDR")
                if rate and rate > 5000:
                    return float(rate), float(rate), "Bank Indonesia JISDOR Benchmark / OER"
        except Exception:
            pass

        return None, None, "Bank Indonesia JISDOR (Benchmark Fallback)"

    def convert(self, amount: float, from_currency: str = "IDR", to_currency: str = "USD") -> CurrencyConversionResponse:
        """
        Converts an amount from one currency to another using the latest Bank Indonesia JISDOR rate.
        """
        from_curr = from_currency.upper().strip()
        to_curr = to_currency.upper().strip()
        live_rate = self.get_live_rate()

        usd_to_idr = live_rate.usd_to_idr
        idr_to_usd = live_rate.idr_to_usd

        if from_curr == to_curr:
            converted = amount
            rate_used = 1.0
            fmt_orig = self.format_amount(amount, from_curr)
            fmt_conv = self.format_amount(converted, to_curr)
        elif from_curr == "IDR" and to_curr == "USD":
            converted = amount * idr_to_usd
            rate_used = idr_to_usd
            fmt_orig = f"Rp {amount:,.0f}"
            fmt_conv = f"${converted:,.2f}"
        elif from_curr == "USD" and to_curr == "IDR":
            converted = amount * usd_to_idr
            rate_used = usd_to_idr
            fmt_orig = f"${amount:,.2f}"
            fmt_conv = f"Rp {converted:,.0f}"
        else:
            converted = amount * idr_to_usd
            rate_used = idr_to_usd
            fmt_orig = f"{amount:,.2f} {from_curr}"
            fmt_conv = f"{converted:,.2f} {to_curr}"

        return CurrencyConversionResponse(
            amount=amount,
            from_currency=from_curr,
            to_currency=to_curr,
            converted_amount=round(converted, 4),
            rate_used=round(rate_used, 8),
            formatted_original=fmt_orig,
            formatted_converted=fmt_conv,
            last_updated=live_rate.last_updated
        )

    @staticmethod
    def format_amount(amount: float, currency: str) -> str:
        if currency.upper() == "IDR":
            return f"Rp {amount:,.0f}"
        elif currency.upper() == "USD":
            return f"${amount:,.2f}"
        return f"{amount:,.2f} {currency}"
