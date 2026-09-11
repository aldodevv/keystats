"""
Domain models for High-Conviction Stock Purchase Analysis:
Margin of Safety, Multi-Scenario Valuation, 10-Point Buy Conviction Checklist,
Position Sizing & Money Management, and Sector Relative Ranking.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class BuyZone(str, Enum):
    STRONG_ACCUMULATION = "STRONG ACCUMULATION"  # Diskon >= 25%, Margin of Safety sangat tinggi
    MODERATE_BUY = "MODERATE BUY"                # Diskon 10% - 24%, Area beli bertahap
    FAIR_HOLD = "FAIR / HOLD"                    # Diskon -5% s.d. +9%, Harga wajar
    OVERVALUED_TRIM = "OVERVALUED / TRIM"        # Diskon < -5%, Terlalu mahal / overbought


class ConvictionTier(str, Enum):
    HIGH_CONVICTION = "HIGH CONVICTION"          # 8 - 10 poin lolos (>= 80%)
    MODERATE_CONVICTION = "MODERATE CONVICTION"  # 5 - 7 poin lolos (50% - 79%)
    LOW_CONVICTION = "LOW CONVICTION"            # 3 - 4 poin lolos (30% - 49%)
    AVOID = "AVOID"                              # < 3 poin lolos (< 30%)


class ConvictionCheckItem(BaseModel):
    id: str
    title: str
    category: str
    passed: bool
    score_weight: float = 10.0
    actual_value_str: str
    benchmark_threshold_str: str
    explanation: str


class MultiScenarioValuation(BaseModel):
    current_price: float
    bear_case_price: float          # Worst-case floor (Safety support)
    base_case_price: float          # Realistic fair value consensus
    bull_case_price: float          # Optimistic expansion target
    margin_of_safety_pct: float     # (Base - Price) / Base * 100
    downside_risk_pct: float        # (Price - Bear) / Price * 100
    upside_potential_pct: float     # (Base - Price) / Price * 100
    bull_upside_pct: float          # (Bull - Price) / Price * 100
    risk_to_reward_ratio: float     # (Bull - Price) / (Price - Bear)
    buy_zone: BuyZone
    buy_zone_label: str
    buy_zone_description: str


class PositionSizingAdvice(BaseModel):
    max_portfolio_allocation_pct: float  # e.g., 15% - 20% of total portfolio
    take_profit_1: float                 # TP 1 (Base Case Target)
    take_profit_2: float                 # TP 2 (Bull Case Target)
    stop_loss_invalidation: float        # Fundamental Invalidation Floor
    allocation_rationale: str
    invalidation_triggers: List[str] = Field(default_factory=list)


class SectorPeerRanking(BaseModel):
    sector_name: str
    total_peers_evaluated: int
    per_percentile: float         # 0-100 (Lower PER = better rank)
    roe_percentile: float         # 0-100 (Higher ROE = better rank)
    dividend_percentile: float    # 0-100 (Higher Yield = better rank)
    badges: List[str] = Field(default_factory=list)


class BuyConvictionReport(BaseModel):
    ticker: str
    conviction_score: float = Field(ge=0, le=100, description="0 to 100% Buy Conviction Score")
    conviction_tier: ConvictionTier
    passed_checks_count: int
    total_checks_count: int = 10
    checklist: List[ConvictionCheckItem] = Field(default_factory=list)
    scenarios: MultiScenarioValuation
    position_sizing: PositionSizingAdvice
    sector_ranking: Optional[SectorPeerRanking] = None
    summary_verdict: str
