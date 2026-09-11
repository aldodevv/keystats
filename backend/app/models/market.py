"""
Domain models for Market Summary & Top Daily Stock Picks (Rekomendasi Terbaik Esok Hari).
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.screener import EmitenSummaryItem


class TopPickItem(BaseModel):
    ticker: str
    name: str
    sector: str
    category: str  # e.g. "TOP_PICK_OVERALL", "BEST_VALUE", "HIGH_QUALITY_MOAT", "DIVIDEND_CASH_COW", "GROWTH_MOMENTUM"
    category_title: str
    category_tag: str
    badge_color: str  # Tailwind color key: "emerald", "indigo", "cyan", "amber", "rose"
    current_price: float
    fair_value: float
    upside_pct: float
    composite_score: float
    grade: str
    verdict: str
    per: float
    pbv: float
    roe: float
    piotroski_f_score: int
    altman_z_score: float
    dividend_yield: float
    key_metrics_summary: List[str]
    rationale: List[str]
    catalyst: str
    entry_zone: Optional[str] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_to_reward_ratio: Optional[float] = None
    buy_zone_label: Optional[str] = None
    max_allocation_pct: Optional[float] = None


class MarketOverviewStats(BaseModel):
    total_emitens: int
    undervalued_count: int
    overvalued_count: int
    fair_count: int
    avg_composite_score: float
    avg_per: float
    avg_pbv: float
    avg_roe: float
    avg_dividend_yield: float
    top_sector: str
    top_sector_count: int


class MarketSummaryResponse(BaseModel):
    stats: MarketOverviewStats
    top_picks: List[TopPickItem]
    emitens: List[EmitenSummaryItem]
    generated_at_desc: str
