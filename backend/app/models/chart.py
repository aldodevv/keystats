"""
Domain models for Candlestick Charts, Technical Analysis, and Indicator Patterns:
OHLCV, Breakout, Gap, Support/Resistance, Moving Averages, RSI, and Fundamental Overlays.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TechnicalSignalType(str, Enum):
    BREAKOUT_BUY = "BREAKOUT BUY"
    BREAKDOWN_SELL = "BREAKDOWN SELL"
    GAP_UP = "GAP UP"
    GAP_DOWN = "GAP DOWN"
    GOLDEN_CROSS = "GOLDEN CROSS (BULLISH)"
    DEATH_CROSS = "DEATH CROSS (BEARISH)"
    RSI_OVERSOLD = "RSI OVERSOLD (BUY ZONE)"
    RSI_OVERBOUGHT = "RSI OVERBOUGHT (TRIM ZONE)"
    SUPPORT_BOUNCE = "SUPPORT BOUNCE"
    RESISTANCE_REJECTION = "RESISTANCE REJECTION"


class CandleDataPoint(BaseModel):
    time: str                      # Format: YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int


class TechnicalSignal(BaseModel):
    date: str
    price: float
    signal_type: TechnicalSignalType
    title: str
    description: str
    color: str = "#10b981"         # Hex color for chart marker
    position: str = "belowBar"     # 'aboveBar' or 'belowBar'
    shape: str = "arrowUp"         # 'arrowUp', 'arrowDown', 'circle'


class SupportResistanceLevel(BaseModel):
    price: float
    kind: str                      # 'SUPPORT' or 'RESISTANCE'
    strength: int = 1              # Number of touches/tests
    description: str


class GapLevel(BaseModel):
    date: str
    gap_type: str                  # 'GAP_UP' or 'GAP_DOWN'
    gap_bottom: float
    gap_top: float
    is_filled: bool = False


class TechnicalIndicators(BaseModel):
    ema_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    trend_summary: str = "BULLISH"
    momentum_summary: str = "NEUTRAL"


class FundamentalOverlay(BaseModel):
    fair_value_tp1: float
    bull_target_tp2: float
    bear_floor_sl: float
    accumulation_zone_top: float
    accumulation_zone_bottom: float


class ChartResponse(BaseModel):
    ticker: str
    name: str
    timeframe: str                 # '1mo', '3mo', '6mo', '1y', '5y'
    current_price: float
    candles: List[CandleDataPoint] = Field(default_factory=list)
    signals: List[TechnicalSignal] = Field(default_factory=list)
    support_resistance: List[SupportResistanceLevel] = Field(default_factory=list)
    gaps: List[GapLevel] = Field(default_factory=list)
    indicators: TechnicalIndicators
    fundamental_overlays: Optional[FundamentalOverlay] = None
