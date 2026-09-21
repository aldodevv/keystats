"""
News & Market Sentiment Data Models for Indonesian Stocks & Macro Intelligence.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class NewsSentiment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class NewsItem(BaseModel):
    title: str
    link: str
    source: str
    pub_date: str
    time_ago: str = ""
    sentiment: NewsSentiment = NewsSentiment.NEUTRAL
    catalyst_tags: List[str] = Field(default_factory=list)
    ticker: Optional[str] = None


class SentimentSummary(BaseModel):
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    bullish_percentage: float = 0.0
    overall_sentiment: NewsSentiment = NewsSentiment.NEUTRAL


class NewsResponse(BaseModel):
    query_ticker: str
    total_items: int
    sentiment_summary: SentimentSummary
    news: List[NewsItem]
    fetched_at: str
