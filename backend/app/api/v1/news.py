"""
API Router for Real-Time Indonesian Stock News & Market Sentiment.
"""

from fastapi import APIRouter, Query, HTTPException
from app.models.news import NewsResponse
from app.services.news_service import NewsService

router = APIRouter(prefix="/news", tags=["News & Sentiment"])

_news_service = NewsService()


@router.get("/ticker/{ticker}", response_model=NewsResponse)
def get_ticker_news(
    ticker: str,
    max_items: int = Query(15, ge=1, le=50, description="Max news items to return")
):
    """
    Fetches real-time news headlines, sentiment breakdown, and catalyst tags for an IDX stock.
    """
    clean = ticker.upper().replace(".JK", "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    return _news_service.get_ticker_news(clean, max_items=max_items)


@router.get("/market", response_model=NewsResponse)
def get_market_news(
    max_items: int = Query(20, ge=1, le=50, description="Max news items to return")
):
    """
    Fetches market-wide breaking news and macroeconomic headlines for IHSG and IDX.
    """
    return _news_service.get_market_news(max_items=max_items)
