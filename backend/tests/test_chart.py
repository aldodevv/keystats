"""
Unit and Integration Tests for Candlestick Charts, Technical Analysis Engine,
Signals (Breakouts, Gaps), Support/Resistance, and Chart REST API.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.chart import CandleDataPoint, TechnicalSignalType
from app.engines.technical_engine import TechnicalEngine
from app.services.emiten_service import EmitenService
from app.services.chart_service import ChartService


client = TestClient(app)


def test_technical_engine_indicators_calculation():
    # Construct 60 mock candles with an uptrend
    candles = []
    base_price = 1000.0
    for i in range(60):
        price = base_price + (i * 10)
        candles.append(CandleDataPoint(
            time=f"2024-01-{(i%28)+1:02d}",
            open=price - 2,
            high=price + 8,
            low=price - 5,
            close=price,
            volume=1000000 + i * 10000
        ))
        
    indicators, signals, supp_res, gaps = TechnicalEngine.analyze(candles)
    
    assert indicators.ema_20 is not None
    assert indicators.sma_50 is not None
    assert indicators.rsi_14 is not None
    assert 0 <= indicators.rsi_14 <= 100
    assert "BULLISH" in indicators.trend_summary


def test_technical_engine_breakout_detection():
    candles = []
    # 25 flat candles
    for i in range(25):
        candles.append(CandleDataPoint(
            time=f"2024-01-{(i%28)+1:02d}",
            open=1000.0,
            high=1020.0,
            low=980.0,
            close=1000.0,
            volume=1000000
        ))
        
    # Candle 26: Massive breakout above 1020 with 3x volume
    candles.append(CandleDataPoint(
        time="2024-02-01",
        open=1010.0,
        high=1100.0,
        low=1005.0,
        close=1090.0,
        volume=3500000
    ))
    
    signals = TechnicalEngine.detect_signals(candles)
    breakouts = [s for s in signals if s.signal_type == TechnicalSignalType.BREAKOUT_BUY]
    assert len(breakouts) >= 1
    assert breakouts[0].price == 1090.0
    assert breakouts[0].shape == "arrowUp"


def test_technical_engine_gap_detection():
    candles = [
        CandleDataPoint(time="2024-01-01", open=1000.0, high=1020.0, low=980.0, close=1010.0, volume=1000000),
        # Gap up: low 1050 > prev high 1020 by > 1.5%
        CandleDataPoint(time="2024-01-02", open=1060.0, high=1080.0, low=1050.0, close=1070.0, volume=1500000),
    ]
    gaps = TechnicalEngine.detect_gaps(candles)
    assert len(gaps) >= 1
    assert gaps[0].gap_type == "GAP_UP"
    assert gaps[0].gap_bottom == 1020.0
    assert gaps[0].gap_top == 1050.0


def test_chart_service_single_emiten():
    emiten_service = EmitenService()
    chart_service = ChartService(emiten_service)
    
    resp = chart_service.get_chart_data("BBRI", timeframe="1y")
    assert resp is not None
    assert resp.ticker == "BBRI"
    assert len(resp.candles) > 10
    assert resp.indicators.ema_20 is not None
    assert resp.indicators.rsi_14 is not None
    assert resp.fundamental_overlays is not None
    assert resp.fundamental_overlays.fair_value_tp1 > 0
    assert resp.fundamental_overlays.bull_target_tp2 >= resp.fundamental_overlays.fair_value_tp1
    assert resp.fundamental_overlays.bear_floor_sl <= resp.fundamental_overlays.fair_value_tp1


def test_chart_api_endpoint_success():
    resp = client.get("/api/v1/chart/BBRI?timeframe=6mo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "BBRI"
    assert data["timeframe"] == "6mo"
    assert len(data["candles"]) > 0
    assert "indicators" in data
    assert "signals" in data
    assert "support_resistance" in data
    assert "fundamental_overlays" in data


def test_chart_api_endpoint_invalid_timeframe():
    resp = client.get("/api/v1/chart/BBRI?timeframe=10y")
    assert resp.status_code == 422  # Validation error on regex
