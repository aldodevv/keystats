"""
FastAPI Endpoints for Quantitative Screener and Presets.
"""

from fastapi import APIRouter, Query
from typing import List, Dict, Optional
from app.services.emiten_service import EmitenService
from app.services.screener_service import ScreenerService
from app.models.screener import (
    ScreenerCriteria,
    ScreenerResponse,
    ScreenerPreset,
    PriceRecommendationItem,
    PriceTierRecommendationResponse
)

router = APIRouter(prefix="/screener", tags=["Quantitative Screener"])
emiten_service = EmitenService()
screener_service = ScreenerService(emiten_service)


@router.post("/run", response_model=ScreenerResponse)
def run_screener(criteria: ScreenerCriteria):
    """Runs the multi-factor screener against all emitens with customizable criteria and price ranges."""
    return screener_service.run_screener(criteria)


@router.get("/recommend-by-price", response_model=List[PriceRecommendationItem])
def recommend_by_price(
    min_price: Optional[float] = Query(None, description="Minimum stock price in IDR"),
    max_price: Optional[float] = Query(None, description="Maximum stock price in IDR"),
    min_score: float = Query(60.0, description="Minimum composite fundamental score (0-100)"),
    only_buy: bool = Query(True, description="Filter only BUY and STRONG BUY recommendations"),
    sector: Optional[str] = Query(None, description="Optional sector filter"),
    sort_by: str = Query("composite_score", description="Sort by: composite_score, price_asc, price_desc, upside_pct, dividend_yield, roe"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of recommendations to return")
):
    """Search and recommend the best stocks within a target price budget."""
    return screener_service.get_recommendations_by_price(
        min_price=min_price,
        max_price=max_price,
        min_score=min_score,
        only_buy=only_buy,
        sector=sector,
        sort_by=sort_by,
        limit=limit
    )


@router.get("/price-tiers", response_model=PriceTierRecommendationResponse)
def get_price_tiers():
    """Returns curated stock recommendations grouped into 3 distinct price tiers (Budget, Mid-Range, Premium Bluechips)."""
    return screener_service.get_price_tier_recommendations()


@router.get("/presets")
def get_presets() -> List[Dict[str, str]]:
    """Returns available screener preset strategies with their rationale."""
    return [
        {
            "id": ScreenerPreset.BUFFETT_MOAT.value,
            "name": "Buffett Quality Moat",
            "description": "High ROE (>14%), low debt (DER < 1.0x), strong Piotroski F-Score (>=6), and positive Free Cash Flow."
        },
        {
            "id": ScreenerPreset.DIVIDEND_CASH_COW.value,
            "name": "Dividend Cash Cow",
            "description": "High dividend yield (>4.5%), safe payout ratio (<80%), safe Altman Z-Score, and positive FCF."
        },
        {
            "id": ScreenerPreset.GARP.value,
            "name": "GARP (Growth At Reasonable Price)",
            "description": "Attractive PEG ratio (<1.2x), solid EPS growth (>8%), and robust ROE (>10%)."
        },
        {
            "id": ScreenerPreset.DEEP_VALUE.value,
            "name": "Deep Value & Turnaround",
            "description": "Low PBV (<1.5x), low PER (<12x), upside potential (>15%), with no bankruptcy risk."
        },
        {
            "id": ScreenerPreset.MOMENTUM_QUALITY.value,
            "name": "Momentum & Quality Growth",
            "description": "Double-digit EPS growth (>10%), top revenue expansion, and high operating efficiency."
        },
        {
            "id": ScreenerPreset.AFFORDABLE_GEMS.value,
            "name": "Affordable Gems (<= Rp 2.500)",
            "description": "Saham terjangkau harga <= Rp 2.500 dengan skor fundamental tinggi (>60), ROE sehat (>12%), dan neraca aman."
        },
        {
            "id": ScreenerPreset.UNDERVALUED_DEALS.value,
            "name": "Undervalued BUY Recommendations",
            "description": "Saham terdiskon dengan rekomendasi BUY / STRONG BUY, potensi upside >10%, dan skor di atas 65."
        }
    ]
