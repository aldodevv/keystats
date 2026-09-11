"""
Domain models for IDX Emiten Shareholder / Stakeholder Ownership Composition.

Combines two authoritative real-data perspectives:
  1. Registered shareholder composition (percentage owned) from company filings / EODHD SharesStats & Holders.
  2. KSEI Single Investor Identification (SID) statistics for retail participation depth.

No synthetic or fabricated values are produced by these models; fields remain
None/empty when the underlying real source does not provide the datum.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ShareholderEntry(BaseModel):
    """A single registered shareholder or holder line item."""
    name: str = Field(description="Shareholder / holder legal name")
    category: Optional[str] = Field(
        default=None,
        description="Holder category (e.g. Institution, Fund, Insider, Public/Free Float, Government, Founder)"
    )
    shares: Optional[float] = Field(default=None, description="Number of shares held")
    percentage: Optional[float] = Field(default=None, description="Ownership percentage of total shares (%)")
    is_controlling: bool = Field(default=False, description="Whether this holder is a controlling shareholder (>50%)")
    filing_date: Optional[str] = Field(default=None, description="As-of / report date for this ownership record")


class SharesStatistics(BaseModel):
    """Share structure statistics (from real SharesStats block)."""
    shares_outstanding: Optional[float] = Field(default=None, description="Total shares outstanding")
    shares_float: Optional[float] = Field(default=None, description="Free-float shares available to the public")
    float_percentage: Optional[float] = Field(default=None, description="Free float as % of shares outstanding")
    percent_insiders: Optional[float] = Field(default=None, description="% held by insiders / controlling parties")
    percent_institutions: Optional[float] = Field(default=None, description="% held by institutions")
    shares_short: Optional[float] = Field(default=None, description="Shares sold short (if reported)")


class SIDStatistics(BaseModel):
    """
    KSEI Single Investor Identification (SID) statistics.
    SID reflects the number of unique registered capital-market investors in Indonesia.
    Populated only when a real KSEI statistics source is configured.
    """
    total_sid: Optional[int] = Field(default=None, description="Total registered SID (all capital market instruments)")
    equity_sid: Optional[int] = Field(default=None, description="SID holding equities/stocks")
    as_of_date: Optional[str] = Field(default=None, description="Reporting period of the SID statistic")
    source: Optional[str] = Field(default=None, description="Data source, e.g. 'KSEI'")


class OwnershipBreakdown(BaseModel):
    """
    Full shareholder / stakeholder ownership report for a single emiten.
    All values originate from real data providers; absent data is left None/empty.
    """
    ticker: str
    name: str
    as_of_date: Optional[str] = Field(default=None, description="As-of date of the ownership snapshot")
    source: str = Field(description="Origin of the ownership data (e.g. 'EODHD', 'IDX', 'KSEI')")

    shares_statistics: Optional[SharesStatistics] = None

    # Aggregate composition percentages
    public_float_pct: Optional[float] = Field(default=None, description="Public / free-float ownership (%)")
    insider_pct: Optional[float] = Field(default=None, description="Insider / controlling ownership (%)")
    institution_pct: Optional[float] = Field(default=None, description="Institutional ownership (%)")
    government_pct: Optional[float] = Field(default=None, description="Government ownership (%)")

    # Detailed holders
    major_shareholders: List[ShareholderEntry] = Field(
        default_factory=list, description="Registered major/controlling shareholders"
    )
    institutional_holders: List[ShareholderEntry] = Field(
        default_factory=list, description="Institutional holders"
    )
    fund_holders: List[ShareholderEntry] = Field(
        default_factory=list, description="Mutual fund / ETF holders"
    )

    # Retail participation
    sid_statistics: Optional[SIDStatistics] = None

    # Data quality / provenance flags
    is_real_data: bool = Field(default=True, description="True when sourced from a live real provider")
    notes: List[str] = Field(default_factory=list, description="Provenance or data-availability notes")
