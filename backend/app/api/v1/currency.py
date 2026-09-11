"""
FastAPI Router for Real-time Currency Exchange Rates and IDR/USD Conversions.
"""

from fastapi import APIRouter, Query
from app.models.currency import CurrencyRateResponse, CurrencyConversionRequest, CurrencyConversionResponse
from app.services.currency_service import CurrencyService

router = APIRouter(prefix="/currency", tags=["Currency & Forex Conversions"])
currency_service = CurrencyService()


@router.get("/rate", response_model=CurrencyRateResponse)
def get_exchange_rate(refresh: bool = Query(False, description="Force refresh from live provider")):
    """
    Returns the latest live USD/IDR and IDR/USD exchange rates with timestamp and source.
    """
    return currency_service.get_live_rate(force_refresh=refresh)


@router.get("/convert", response_model=CurrencyConversionResponse)
def convert_currency_get(
    amount: float = Query(..., gt=0, description="Amount to convert"),
    from_currency: str = Query("IDR", description="Source currency code (IDR or USD)"),
    to_currency: str = Query("USD", description="Target currency code (USD or IDR)")
):
    """
    Converts amount between IDR and USD using the latest live exchange rate.
    """
    return currency_service.convert(
        amount=amount,
        from_currency=from_currency,
        to_currency=to_currency
    )


@router.post("/convert", response_model=CurrencyConversionResponse)
def convert_currency_post(request: CurrencyConversionRequest):
    """
    Converts currency via JSON request body payload.
    """
    return currency_service.convert(
        amount=request.amount,
        from_currency=request.from_currency,
        to_currency=request.to_currency
    )
