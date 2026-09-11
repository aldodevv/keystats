"""
FastAPI Endpoints for Peer Comparison Matrix.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.emiten_service import EmitenService
from app.services.comparison_service import ComparisonService
from app.models.screener import ComparisonResponse

router = APIRouter(prefix="/compare", tags=["Peer Comparison"])
emiten_service = EmitenService()
comparison_service = ComparisonService(emiten_service)


class CompareRequest(BaseModel):
    tickers: List[str]


@router.post("", response_model=ComparisonResponse)
def compare_emitens(req: CompareRequest):
    """Compares multiple emitens side-by-side and returns champion rankings."""
    if not req.tickers:
        raise HTTPException(status_code=400, detail="Must provide at least 1 ticker to compare.")
    return comparison_service.compare_emitens(req.tickers)
