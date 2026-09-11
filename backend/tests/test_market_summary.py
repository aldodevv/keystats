"""
Unit & Integration Tests for Market Summary and Daily Top Stock Picks with Institutional Provider.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.services.emiten_service import EmitenService
from app.services.market_summary_service import MarketSummaryService
from tests.stub_provider import StubDataProvider

client = TestClient(app)


def test_market_summary_service_unit():
    inst_prov = StubDataProvider()
    emiten_srv = EmitenService(provider=inst_prov)
    market_srv = MarketSummaryService(emiten_srv)

    summary = market_srv.get_market_summary()

    # 1. Stats verification
    assert summary.stats.total_emitens > 0
    assert summary.stats.avg_composite_score > 0
    assert summary.stats.avg_roe > 0

    # 2. Emitens list verification
    assert len(summary.emitens) == summary.stats.total_emitens
    # Check that emitens are sorted descending by composite score
    scores = [e.composite_score for e in summary.emitens]
    assert scores == sorted(scores, reverse=True)

    # 3. Top Picks verification
    assert len(summary.top_picks) > 0
    tickers_in_picks = [p.ticker for p in summary.top_picks]
    # Ensure distinct top pick tickers
    assert len(tickers_in_picks) == len(set(tickers_in_picks))

    # Verify attributes of top pick
    for pick in summary.top_picks:
        assert pick.ticker != ""
        assert pick.category != ""
        assert pick.catalyst != ""
        assert pick.fair_value > 0
        assert pick.composite_score > 0
        assert len(pick.key_metrics_summary) > 0


def test_api_get_market_summary():
    response = client.get("/api/v1/market/summary")
    assert response.status_code == 200
    data = response.json()

    assert "stats" in data
    assert "top_picks" in data
    assert "emitens" in data
    assert data["stats"]["total_emitens"] >= 1
    assert len(data["top_picks"]) >= 1


def test_api_get_market_top_picks():
    response = client.get("/api/v1/market/top-picks")
    assert response.status_code == 200
    picks = response.json()

    assert isinstance(picks, list)
    assert len(picks) >= 1
    assert "ticker" in picks[0]
    assert "catalyst" in picks[0]
