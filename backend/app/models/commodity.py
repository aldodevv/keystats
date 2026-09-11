"""
Domain models for Global Commodities, Forex Real-Time Data,
and Scoped IDX Emitens with Fundamental Evaluation.
"""

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class CommodityCategory(str, Enum):
    ENERGY = "ENERGY"
    METALS = "METALS"
    AGRICULTURE = "AGRICULTURE"
    FOREX = "FOREX"


class CorrelationType(str, Enum):
    DIRECT_PRODUCER_BENEFICIARY = "DIRECT_PRODUCER_BENEFICIARY"
    INPUT_COST_SENSITIVE = "INPUT_COST_SENSITIVE"
    FOREX_EXPORTER = "FOREX_EXPORTER"
    FOREX_IMPORTER_DEBTOR = "FOREX_IMPORTER_DEBTOR"


class InvestmentSuitability(str, Enum):
    SANGAT_LAYAK = "SANGAT_LAYAK"           # High score (>=70), undervalued, strong ROE, low DER
    LAYAK_ANALISIS = "LAYAK_ANALISIS"       # Good score (>=60), fair/undervalued, reasonable balance sheet
    NETRAL = "NETRAL"                       # Fairly valued, moderate financials
    SPEKULATIF_WASPADA = "SPEKULATIF_WASPADA" # High debt (DER>2.5), low F-Score, or negative profit
    HINDARI = "HINDARI"                     # Heavy overvaluation or severe financial distress


class CommodityItem(BaseModel):
    id: str                                  # e.g. "GOLD", "COAL", "BRENT_OIL", "CPO", "NICKEL", "USD_IDR"
    symbol: str                              # Market ticker, e.g. "GC=F", "BZ=F", "USDIDR=X"
    name: str                                # e.g. "Emas Dunia (Gold)", "Minyak Brent"
    category: CommodityCategory
    price: float
    previous_close: float
    change_24h: float
    change_pct_24h: float
    unit: str                                # e.g. "USD/oz", "USD/barrel", "USD/ton", "IDR"
    currency: str                            # e.g. "USD", "IDR"
    last_updated: str
    source: str
    is_positive: bool = True
    related_emitens_count: int = 0
    description: str = ""


class EmitenScopedFundamental(BaseModel):
    ticker: str
    name: str
    sector: str
    current_price: float
    fair_value: float
    upside_pct: float
    composite_score: float
    grade: str
    verdict: str
    per: float
    pbv: float
    roe: float
    der: float
    piotroski_f_score: int
    altman_z_score: float
    dividend_yield: float
    correlation_type: CorrelationType
    impact_direction: str                   # "POSITIF / UNTUNG" vs "NEGATIF / BEBAN BIAYA"
    suitability: InvestmentSuitability
    suitability_label: str
    correlation_thesis: str
    key_strengths: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)


class CommodityDetailResponse(BaseModel):
    commodity: CommodityItem
    total_related_emitens: int
    undervalued_count: int
    top_pick_ticker: Optional[str] = None
    avg_composite_score: float
    emitens: List[EmitenScopedFundamental]


class MacroOverviewResponse(BaseModel):
    total_commodities: int
    total_forex_pairs: int
    commodities: List[CommodityItem]
    forex_pairs: List[CommodityItem]
    top_gainers: List[CommodityItem]
    top_losers: List[CommodityItem]
    market_as_of: str
    data_source_status: str
