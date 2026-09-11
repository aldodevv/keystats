"""
FastAPI Endpoints for Single Emiten Analysis & Search.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.services.emiten_service import EmitenService
from app.models.score import EmitenAnalysisReport
from app.models.keystats import RawKeyStats
from app.models.ownership import OwnershipBreakdown
from app.data_providers.institutional_provider import DataSourceNotConfiguredError

router = APIRouter(prefix="/emiten", tags=["Emiten Analysis"])
emiten_service = EmitenService()


@router.get("/list", response_model=List[str])
def list_tickers():
    """List all available IDX tickers from the live data source."""
    try:
        return emiten_service.list_all_available_tickers()
    except DataSourceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/search", response_model=List[RawKeyStats])
def search_emitens(q: str = Query(..., min_length=1, description="Search query for ticker or company name")):
    """Search emitens by ticker or name."""
    try:
        return emiten_service.search_emitens(q)
    except DataSourceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{ticker}", response_model=EmitenAnalysisReport)
def get_single_emiten_analysis(
    ticker: str,
    price: Optional[float] = Query(None, description="Simulate with custom/override market price (IDR)"),
    live: bool = Query(True, description="Fetch live realtime quote from the IDX data source")
):
    """Calculates full KeyStats, Multi-Model Valuation, and 5-Pillar Score for a single emiten with realtime or simulated price."""
    try:
        report = emiten_service.analyze_single_emiten(ticker, override_price=price, force_live=live)
    except DataSourceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not report:
        raise HTTPException(status_code=404, detail=f"Emiten with ticker '{ticker.upper()}' not found or data unavailable.")
    return report


@router.get("/{ticker}/shareholders", response_model=OwnershipBreakdown)
def get_emiten_shareholders(ticker: str):
    """
    Returns the real shareholder / stakeholder ownership composition for an emiten:
    free float %, insider/institutional %, detailed institutional & fund holders, and
    (when a KSEI source is configured) market-wide SID retail-participation statistics.
    """
    try:
        ownership = emiten_service.get_shareholders(ticker)
    except DataSourceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not ownership:
        raise HTTPException(
            status_code=404,
            detail=f"No shareholder/ownership data available for '{ticker.upper()}' from the configured real data source.",
        )
    return ownership
