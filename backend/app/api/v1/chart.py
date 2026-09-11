"""
Chart and Technical Analysis API Endpoints.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from app.services.emiten_service import EmitenService
from app.services.chart_service import ChartService
from app.models.chart import ChartResponse


router = APIRouter(prefix="/chart", tags=["Chart & Technicals"])


def get_chart_service() -> ChartService:
    emiten_service = EmitenService()
    return ChartService(emiten_service)


@router.get("/{ticker}", response_model=ChartResponse)
def get_stock_chart(
    ticker: str,
    timeframe: str = Query("1y", pattern="^(1mo|3mo|6mo|1y|5y)$", description="Candle timeframe: 1mo, 3mo, 6mo, 1y, 5y"),
    service: ChartService = Depends(get_chart_service)
):
    """
    Returns historical OHLCV candlestick data, moving averages, RSI,
    detected technical signals (Breakouts, Gaps), support/resistance levels,
    and fundamental price overlays (TP1, TP2, Bear Floor).
    """
    data = service.get_chart_data(ticker, timeframe=timeframe)
    if not data:
        raise HTTPException(status_code=404, detail=f"Chart data for ticker '{ticker}' not found.")
    return data
