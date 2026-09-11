"""
Pydantic Models for Currency Exchange Rates and Conversion.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict


class CurrencyRateResponse(BaseModel):
    base_currency: str = Field(default="USD", description="Base currency code")
    target_currency: str = Field(default="IDR", description="Target currency code")
    usd_to_idr: float = Field(description="Exchange rate for 1 USD to IDR")
    idr_to_usd: float = Field(description="Exchange rate for 1 IDR to USD")
    previous_close: Optional[float] = Field(default=None, description="Previous close exchange rate")
    change_24h: Optional[float] = Field(default=None, description="24-hour rate change")
    change_pct_24h: Optional[float] = Field(default=None, description="24-hour rate change in percent")
    last_updated: str = Field(description="ISO timestamp of last update")
    last_updated_formatted: str = Field(description="Human readable update timestamp")
    source: str = Field(description="Data provider source name")
    formatted_rate: str = Field(description="Formatted string e.g. 1 USD = Rp 17,712")


class CurrencyConversionRequest(BaseModel):
    amount: float = Field(gt=0, description="Amount to convert")
    from_currency: str = Field(default="IDR", description="Source currency (IDR or USD)")
    to_currency: str = Field(default="USD", description="Target currency (USD or IDR)")


class CurrencyConversionResponse(BaseModel):
    amount: float = Field(description="Original input amount")
    from_currency: str = Field(description="Source currency code")
    to_currency: str = Field(description="Target currency code")
    converted_amount: float = Field(description="Result of currency conversion")
    rate_used: float = Field(description="Exchange rate used for calculation")
    formatted_original: str = Field(description="Formatted input amount")
    formatted_converted: str = Field(description="Formatted converted amount")
    last_updated: str = Field(description="Exchange rate timestamp")
