"""
Domain models for Economic and Market Calendar Agendas, Affected IDX Stocks, and Scenario Analysis.
"""

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ImpactLevel(str, Enum):
    HIGH = "HIGH"        # 🔴 Dampak Tinggi / 3 Bintang
    MEDIUM = "MEDIUM"    # 🟡 Dampak Sedang / 2 Bintang
    LOW = "LOW"          # 🟢 Dampak Ringan / 1 Bintang


class MarketScope(str, Enum):
    INDONESIA = "INDONESIA"  # 🇮🇩 Domestik
    US_GLOBAL = "US_GLOBAL"  # 🇺🇸 US & Global


class EventCategory(str, Enum):
    INTEREST_RATE = "INTEREST_RATE"          # Suku Bunga & Kebijakan Sentral Bank
    INFLATION_GDP = "INFLATION_GDP"          # Inflasi & Pertumbuhan Ekonomi (GDP)
    COMMODITY_ENERGY = "COMMODITY_ENERGY"    # Komoditas & Energi (Minyak, Batu Bara, Nikel, CPO)
    DIVIDEND = "DIVIDEND"                    # Kalender Dividen & Cum-Date
    CORPORATE_ACTION = "CORPORATE_ACTION"    # RUPS, Buyback, Rilis Lapkeu
    INDEX_REBALANCE = "INDEX_REBALANCE"      # Rebalancing Indeks (MSCI, FTSE, LQ45)
    TRADE_MACRO = "TRADE_MACRO"              # Neraca Perdagangan, Devisa, Rating Kredit


class MarketBias(str, Enum):
    BULLISH = "BULLISH"                      # 🟢 Positif untuk Saham Terdampak
    BEARISH = "BEARISH"                      # 🔴 Negatif / Menekan Saham Terdampak
    NEUTRAL_VOLATILE = "NEUTRAL_VOLATILE"    # 🟡 Dua Arah / Volatilitas Meningkat


class ImpactedStockItem(BaseModel):
    ticker: str
    name: str
    sector: str
    sensitivity: str  # "TINGGI", "SEDANG", "RINGAN"
    expected_bias: MarketBias
    impact_reason: str


class ScenarioItem(BaseModel):
    scenario_name: str
    condition: str
    ihsg_impact: str
    sector_impact: str
    favored_stocks: List[str]
    pressured_stocks: List[str]


class CalendarAgendaItem(BaseModel):
    id: str
    title: str
    country: str  # e.g. "Indonesia", "Amerika Serikat", "Global / OPEC", "China"
    country_code: str  # e.g. "ID", "US", "GLOBAL", "CN"
    flag_emoji: str  # e.g. "🇮🇩", "🇺🇸", "🌐", "🇨🇳"
    institution: str  # e.g. "Bank Indonesia", "Federal Reserve (The Fed)", "BPS", "IDX / Emiten"
    category: EventCategory
    category_label: str
    event_date: str  # YYYY-MM-DD
    time_utc7: str  # e.g. "14:30 WIB", "19:30 WIB", "Tentatif"
    days_until: int  # Dynamic countdown in days (negative if passed)
    relative_time_label: str  # "Hari Ini", "Besok", "Dalam 3 Hari", "Selesai"
    status: str  # "UPCOMING", "TODAY", "COMPLETED"
    impact_level: ImpactLevel
    market_scope: MarketScope
    previous_val: Optional[str] = None
    forecast_val: Optional[str] = None
    actual_val: Optional[str] = None
    unit: Optional[str] = None
    summary: str
    transmission_mechanism: str
    impacted_stocks: List[ImpactedStockItem]
    scenarios: List[ScenarioItem]
    actionable_strategy: str
    is_tentative: bool = False


class SectorSensitivityItem(BaseModel):
    sector_name: str
    icon: str
    primary_catalysts: List[str]
    key_tickers: List[str]
    sensitivity_level: str  # "Sangat Tinggi", "Tinggi", "Sedang"
    macro_exposure: str


class CalendarStats(BaseModel):
    total_events: int
    high_impact_count: int
    domestic_count: int
    us_global_count: int
    total_affected_stocks: int


class CalendarResponse(BaseModel):
    stats: CalendarStats
    agendas: List[CalendarAgendaItem]
    upcoming_highlights: List[CalendarAgendaItem]
    sector_sensitivities: List[SectorSensitivityItem]
    generated_at_desc: str
