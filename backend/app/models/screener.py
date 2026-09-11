"""
Domain models for Screener Filters, Presets, and Comparison.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ScreenerPreset(str, Enum):
    CUSTOM = "CUSTOM"
    BUFFETT_MOAT = "BUFFETT_MOAT"          # High ROIC, Low Debt, High Piotroski
    DIVIDEND_CASH_COW = "DIVIDEND_CASH_COW"  # High Yield, Safe DPR, Positive FCF
    GARP = "GARP"                          # Growth at Reasonable Price (Low PEG, High Growth)
    DEEP_VALUE = "DEEP_VALUE"              # Low PBV/PER, Safe Altman Z
    MOMENTUM_QUALITY = "MOMENTUM_QUALITY"  # High Margin Expansion + Strong EPS Growth
    AFFORDABLE_GEMS = "AFFORDABLE_GEMS"    # Affordable price (<= Rp 2,500), high score, healthy ROE
    UNDERVALUED_DEALS = "UNDERVALUED_DEALS" # Undervalued BUY/STRONG BUY with positive upside


class ScreenerCriteria(BaseModel):
    preset: Optional[ScreenerPreset] = None
    sectors: Optional[List[str]] = None
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    
    # Stock Price Filters (Harga Saham IDR)
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    
    # Valuation Filters
    min_pe: Optional[float] = None
    max_pe: Optional[float] = None
    min_pbv: Optional[float] = None
    max_pbv: Optional[float] = None
    max_peg: Optional[float] = None
    min_upside_pct: Optional[float] = None
    
    # Profitability Filters
    min_roe: Optional[float] = None
    min_npm: Optional[float] = None
    min_roic: Optional[float] = None
    
    # Health & Quality
    max_der: Optional[float] = None
    min_altman_z: Optional[float] = None
    min_piotroski_f: Optional[int] = None
    min_current_ratio: Optional[float] = None
    
    # Dividend & Cash Flow
    min_dividend_yield: Optional[float] = None
    max_dpr: Optional[float] = None
    must_have_positive_fcf: bool = False
    
    # Growth
    min_revenue_growth: Optional[float] = None
    min_eps_growth: Optional[float] = None
    
    # Score & Recommendation Filters
    min_composite_score: Optional[float] = None
    verdicts: Optional[List[str]] = None
    only_undervalued: bool = False
    only_buy_recommendations: bool = False
    
    # Sorting: composite_score, price_asc, price_desc, upside_pct, dividend_yield, roe
    sort_by: Optional[str] = "composite_score"


class EmitenSummaryItem(BaseModel):
    ticker: str
    name: str
    sector: str
    current_price: float
    market_cap: float
    eps: float = 0.0
    revenue: float = 0.0
    revenue_growth: float = 0.0
    eps_growth: float = 0.0
    per: float
    pbv: float
    roe: float
    der: float
    piotroski_f_score: int
    altman_z_score: float
    dividend_yield: float
    composite_score: float
    grade: str
    verdict: str
    upside_pct: float


class ScreenerResponse(BaseModel):
    total_matched: int
    results: List[EmitenSummaryItem]
    applied_preset: Optional[str] = None


class PriceRecommendationItem(BaseModel):
    ticker: str
    name: str
    sector: str
    current_price: float
    eps: float = 0.0
    revenue: float = 0.0
    eps_growth: float = 0.0
    composite_score: float
    grade: str
    verdict: str
    upside_pct: float
    per: float
    pbv: float
    roe: float
    dividend_yield: float
    recommendation_reason: str


class PriceTierGroup(BaseModel):
    tier_id: str
    tier_name: str
    price_range_desc: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    count: int
    items: List[PriceRecommendationItem]


class PriceTierRecommendationResponse(BaseModel):
    total_recommendations: int
    tiers: List[PriceTierGroup]
    generated_at: Optional[str] = None


class ComparisonResponse(BaseModel):
    tickers: List[str]
    items: List[EmitenSummaryItem]
    detailed_reports: List[dict]
    best_in_class: dict  # metric_name -> ticker
