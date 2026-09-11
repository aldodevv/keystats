"""
FastAPI Router for Real-time Global Commodities, Forex Data,
and Scoped IDX Emitens with Fundamental Scoring.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.models.commodity import (
    MacroOverviewResponse,
    CommodityDetailResponse,
)
from app.services.commodity_service import CommodityService

router = APIRouter(prefix="/commodities", tags=["Global Commodities & Forex"])
commodity_service = CommodityService()


@router.get("/overview", response_model=MacroOverviewResponse)
def get_macro_overview(
    refresh: bool = Query(False, description="Force refresh live quotes from global market")
):
    """
    Returns live 1:1 quotes for all tracked global commodities and forex pairs,
    including top gainers, losers, and 24h percentage changes.
    """
    return commodity_service.get_macro_overview(force_refresh=refresh)


@router.get("/{commodity_id}/emitens", response_model=CommodityDetailResponse)
def get_scoped_emitens_for_commodity(
    commodity_id: str,
):
    """
    Retrieves all Indonesian Stock Exchange (IDX) emitens linked to the specified
    commodity or forex pair, complete with institutional fundamental evaluation:
    Composite Score, Valuation, ROE, DER, Piotroski F-Score, and Investment Suitability.
    """
    detail = commodity_service.get_commodity_scoped_emitens(commodity_id=commodity_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Commodity or Forex with ID '{commodity_id}' is not recognized."
        )
    return detail
