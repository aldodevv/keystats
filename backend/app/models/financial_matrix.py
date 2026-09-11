"""
Stockbit-Grade Financial Statement Matrix Domain Models.
Supports Multi-Year Quarterly Breakdowns (2020 - 2026+), TTM Aggregations,
Annualised Projections, Per-Share Metrics, and Balance Sheet breakdowns.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class QuarterlyDataPoint(BaseModel):
    q1: Optional[float] = None
    q2: Optional[float] = None
    q3: Optional[float] = None
    q4: Optional[float] = None
    annualised: Optional[float] = None
    ttm: Optional[float] = None
    dividend_ttm: Optional[float] = None
    payout_ratio_pct: Optional[float] = None
    dividend_yield_pct: Optional[float] = None


class IncomeStatementTTM(BaseModel):
    revenue_ttm: float = 0.0
    gross_profit_ttm: float = 0.0
    ebitda_ttm: float = 0.0
    net_income_ttm: float = 0.0


class BalanceSheetQuarter(BaseModel):
    cash: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    working_capital: float = 0.0
    common_equity: float = 0.0
    long_term_debt: float = 0.0
    short_term_debt: float = 0.0
    total_debt: float = 0.0
    net_debt: float = 0.0
    total_equity: float = 0.0


class PerShareFinancials(BaseModel):
    eps_ttm: float = 0.0
    eps_annualised: float = 0.0
    revenue_per_share_ttm: float = 0.0
    cash_per_share: float = 0.0
    book_value_per_share: float = 0.0
    fcf_per_share_ttm: float = 0.0


class StockbitFinancialMatrix(BaseModel):
    years: List[int] = Field(default_factory=lambda: [2026, 2025, 2024, 2023, 2022, 2021, 2020])
    currency: str = "IDR"
    
    # Matrices: Year string -> QuarterlyDataPoint
    net_income_matrix: Dict[str, QuarterlyDataPoint] = Field(default_factory=dict)
    eps_matrix: Dict[str, QuarterlyDataPoint] = Field(default_factory=dict)
    revenue_matrix: Dict[str, QuarterlyDataPoint] = Field(default_factory=dict)
    
    # Side Breakdown Panels (Stockbit-Grade)
    income_statement_ttm: IncomeStatementTTM = Field(default_factory=IncomeStatementTTM)
    balance_sheet_quarter: BalanceSheetQuarter = Field(default_factory=BalanceSheetQuarter)
    per_share_metrics: PerShareFinancials = Field(default_factory=PerShareFinancials)
