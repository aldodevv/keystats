"""
Chart Service: Orchestrates historical corporate-action adjusted OHLCV data retrieval,
technical indicators calculation, signal detection, and fundamental overlay generation.
Ensures adjusted series is used to eliminate false EMA/SMA crossover signals.
"""

from typing import Optional, List
from app.data_providers.base import BaseDataProvider
from app.services.emiten_service import EmitenService
from app.engines.technical_engine import TechnicalEngine
from app.models.chart import (
    ChartResponse,
    CandleDataPoint,
    FundamentalOverlay,
    TechnicalIndicators
)


class ChartService:
    def __init__(self, emiten_service: EmitenService):
        self.emiten_service = emiten_service
        self.provider: BaseDataProvider = emiten_service.provider

    def get_chart_data(self, ticker: str, timeframe: str = "1y") -> Optional[ChartResponse]:
        clean_ticker = ticker.upper().replace(".JK", "").strip()
        
        # 1. Fetch Corporate-Action Adjusted OHLCV Candlestick data from Institutional Provider
        candles = self.provider.get_historical_ohlcv(clean_ticker, timeframe=timeframe)
        if not candles:
            return None
            
        current_price = candles[-1].close if candles else 0.0
        
        # 2. Run Technical Pattern Engine (EMA 20, SMA 50, RSI 14, MACD, Breakouts, Gaps)
        indicators, signals, support_resistance, gaps = TechnicalEngine.analyze(candles)
        
        # 3. Retrieve Fundamental Overlays from Emiten Analysis
        report = self.emiten_service.analyze_single_emiten(clean_ticker)
        overlays: Optional[FundamentalOverlay] = None
        emiten_name = clean_ticker
        
        if report:
            emiten_name = report.name
            current_price = report.current_price
            
            # Extract fundamental targets
            tp1 = report.valuation.average_fair_value
            if report.buy_conviction:
                sc = report.buy_conviction.scenarios
                tp1 = sc.base_case_price
                tp2 = sc.bull_case_price
                bear_sl = sc.bear_case_price
                accum_top = tp1 * 0.85      # 15% discount
                accum_bottom = bear_sl
            else:
                tp2 = tp1 * 1.25
                bear_sl = tp1 * 0.75
                accum_top = tp1 * 0.85
                accum_bottom = bear_sl
                
            overlays = FundamentalOverlay(
                fair_value_tp1=round(tp1, 2),
                bull_target_tp2=round(tp2, 2),
                bear_floor_sl=round(bear_sl, 2),
                accumulation_zone_top=round(accum_top, 2),
                accumulation_zone_bottom=round(accum_bottom, 2)
            )

        return ChartResponse(
            ticker=clean_ticker,
            name=emiten_name,
            timeframe=timeframe,
            current_price=current_price,
            candles=candles,
            signals=signals,
            support_resistance=support_resistance,
            gaps=gaps,
            indicators=indicators,
            fundamental_overlays=overlays
        )
