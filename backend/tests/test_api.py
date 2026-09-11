"""
Integration tests for FastAPI endpoints (Emiten, Compare, Screener).
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_get_single_emiten():
    resp = client.get("/api/v1/emiten/BBRI")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "BBRI"
    assert "valuation" in data
    assert "profitability" in data
    assert "solvency" in data
    assert "composite_score" in data
    assert data["composite_score"] > 0
    assert data["grade"] in ["A+", "A", "B", "C", "D", "F"]


def test_compare_emitens():
    resp = client.post("/api/v1/compare", json={"tickers": ["BBCA", "BBRI", "BMRI"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    assert "best_in_class" in data
    assert "overall_champion" in data["best_in_class"]


def test_screener_presets():
    resp = client.get("/api/v1/screener/presets")
    assert resp.status_code == 200
    presets = resp.json()
    assert len(presets) >= 4


def test_screener_run_buffett_moat():
    resp = client.post("/api/v1/screener/run", json={"preset": "BUFFETT_MOAT"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["total_matched"] >= 1


def test_stock_permalink_route():
    resp = client.get("/stock/BBRI")
    assert resp.status_code == 200
    assert "BRIGHTS" in resp.text
    assert "<html" in resp.text

    resp_head = client.head("/stock/BBCA")
    assert resp_head.status_code == 200
