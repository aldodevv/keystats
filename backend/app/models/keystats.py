"""
Domain data models for IDX Emiten Financial Statements, KeyStats, and Sector Attributes.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.xbrl import XBRLEntryPoint


class FinancialPeriod(BaseModel):
    year: int
    quarter: Optional[int] = None
    filing_date: Optional[str] = None  # Point-in-time filing timestamp to prevent look-ahead bias
    xbrl_entry_point: Optional[XBRLEntryPoint] = None
    
    revenue: float = 0.0
    gross_profit: float = 0.0
    operating_profit: float = 0.0
    ebit: float = 0.0
    ebitda: float = 0.0
    net_income: float = 0.0
    eps: float = 0.0
    
    total_assets: float = 0.0
    current_assets: float = 0.0
    cash_and_equivalents: float = 0.0
    inventory: float = 0.0
    receivables: float = 0.0
    total_liabilities: float = 0.0
    current_liabilities: float = 0.0
    total_debt: float = 0.0
    short_term_debt: float = 0.0
    long_term_debt: float = 0.0
    total_equity: float = 0.0
    retained_earnings: float = 0.0
    
    cfo: float = 0.0  # Cash Flow from Operations
    capex: float = 0.0  # Capital Expenditure
    fcf: float = 0.0  # Free Cash Flow
    dividends_paid: float = 0.0
    shares_outstanding: float = 0.0

    # Bank-Specific Detailed XBRL Items (OJK & Bank Indonesia Reporting)
    interest_income: float = 0.0
    interest_expense: float = 0.0
    net_interest_income: float = 0.0
    earning_assets: float = 0.0
    total_loans: float = 0.0
    deposits_dpk: float = 0.0
    casa_deposits: float = 0.0
    npl_gross_amount: float = 0.0
    npl_net_amount: float = 0.0
    loan_loss_provisions: float = 0.0
    regulatory_capital: float = 0.0
    risk_weighted_assets: float = 0.0


class BankSpecificMetrics(BaseModel):
    car: Optional[float] = None  # Capital Adequacy Ratio (%)
    npl_gross: Optional[float] = None  # Non-Performing Loan Gross (%)
    npl_net: Optional[float] = None  # Non-Performing Loan Net (%)
    nim: Optional[float] = None  # Net Interest Margin (%)
    bopo: Optional[float] = None  # Biaya Operasional thd Pendapatan Operasional (%)
    ldr: Optional[float] = None  # Loan to Deposit Ratio (%)
    casa: Optional[float] = None  # Current Account Saving Account ratio (%)
    cost_of_credit: Optional[float] = None  # CoC (%)
    earning_assets: Optional[float] = None
    total_loans: Optional[float] = None
    deposits_dpk: Optional[float] = None


from app.models.financial_matrix import StockbitFinancialMatrix


class RawKeyStats(BaseModel):
    ticker: str = Field(description="IDX Stock Ticker (e.g. BBRI, ASII, ADRO)")
    name: str = Field(description="Company Full Name")
    sector: str = Field(default="General", description="IDX Sector")
    industry: str = Field(default="General", description="IDX Sub-industry")
    xbrl_entry_point: XBRLEntryPoint = Field(default=XBRLEntryPoint.GENERAL_INDUSTRY, description="XBRL Taxonomy Entry Point")
    
    # Price & Market Information
    current_price: float = Field(description="Latest Closing / Current Price (IDR)")
    previous_close: Optional[float] = Field(default=None, description="Previous Day Closing Price (IDR)")
    price_change_pct: Optional[float] = Field(default=0.0, description="Price change vs previous close in %")
    is_realtime: bool = Field(default=True, description="Whether price is from live realtime quote")
    last_updated_time: Optional[str] = Field(default=None, description="Timestamp of price quote")
    shares_outstanding: float = Field(description="Total Listed Shares")
    market_cap: float = Field(description="Market Capitalization (IDR)")
    
    # Financial Statements (Current & Previous for YoY / Piotroski / Altman)
    current_period: FinancialPeriod
    previous_period: Optional[FinancialPeriod] = None
    historical_periods: List[FinancialPeriod] = Field(default_factory=list)
    
    # Stockbit-Grade Multi-Year Quarterly Financial Matrix (2020-2026+)
    financial_matrix: Optional[StockbitFinancialMatrix] = None
    
    # Market & Valuation raw indicators
    dps: float = 0.0  # Dividend per share
    beta: float = 1.0
    pe_standard_deviation: Optional[float] = None
    pe_mean_5y: Optional[float] = None
    pbv_mean_5y: Optional[float] = None
    pbv_standard_deviation: Optional[float] = None
    
    # Banking metrics if sector is Financials/Bank
    bank_metrics: Optional[BankSpecificMetrics] = None
    
    # Additional flags
    is_syariah: bool = False
    idx_board: str = "Main"  # Main, Development, Acceleration, New Economy

