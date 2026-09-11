"""
FastAPI Router for Market Summary and Daily Top Stock Picks.
"""

from fastapi import APIRouter
from typing import List
from app.services.emiten_service import EmitenService
from app.services.market_summary_service import MarketSummaryService
from app.models.market import MarketSummaryResponse, TopPickItem

router = APIRouter(prefix="/market", tags=["Market Overview & Top Picks"])

emiten_service = EmitenService()
market_service = MarketSummaryService(emiten_service)


@router.get("/summary", response_model=MarketSummaryResponse)
def get_market_summary():
    """
    Returns market-wide fundamental overview, statistical aggregations,
    and curated top daily stock picks for tomorrow.
    """
    return market_service.get_market_summary()


@router.get("/top-picks", response_model=List[TopPickItem])
def get_top_picks():
    """
    Returns curated best stock picks for tomorrow across categories (Overall Best, Deep Value, Quality Moat, Dividend Cash Cow).
    """
    summary = market_service.get_market_summary()
    return summary.top_picks
