"""
Unit and Integration Tests for Price-Based Screener and Stock Recommendations.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.emiten_service import EmitenService
from app.services.screener_service import ScreenerService
from app.models.screener import ScreenerCriteria, ScreenerPreset

client = TestClient(app)


def test_screener_presets_include_new():
    resp = client.get("/api/v1/screener/presets")
    assert resp.status_code == 200
    presets = resp.json()
    preset_ids = [p["id"] for p in presets]
    assert "AFFORDABLE_GEMS" in preset_ids
    assert "UNDERVALUED_DEALS" in preset_ids


def test_screener_filter_by_max_price():
    resp = client.post("/api/v1/screener/run", json={"max_price": 5000.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matched"] > 0
    for item in data["results"]:
        assert item["current_price"] <= 5000.0


def test_screener_filter_by_min_and_max_price():
    resp = client.post("/api/v1/screener/run", json={"min_price": 1000.0, "max_price": 5000.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matched"] > 0
    for item in data["results"]:
        assert 1000.0 <= item["current_price"] <= 5000.0


def test_screener_sort_by_price_asc():
    resp = client.post("/api/v1/screener/run", json={"sort_by": "price_asc"})
    assert resp.status_code == 200
    data = resp.json()
    results = data["results"]
    assert len(results) >= 2
    prices = [r["current_price"] for r in results]
    assert prices == sorted(prices)


def test_screener_sort_by_price_desc():
    resp = client.post("/api/v1/screener/run", json={"sort_by": "price_desc"})
    assert resp.status_code == 200
    data = resp.json()
    results = data["results"]
    assert len(results) >= 2
    prices = [r["current_price"] for r in results]
    assert prices == sorted(prices, reverse=True)


def test_screener_preset_affordable_gems():
    resp = client.post("/api/v1/screener/run", json={"preset": "AFFORDABLE_GEMS"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied_preset"] == "AFFORDABLE_GEMS"
    for item in data["results"]:
        assert item["current_price"] <= 2500.0
        assert item["composite_score"] >= 60.0
        assert item["roe"] >= 12.0


def test_screener_buy_only_filter():
    resp = client.post("/api/v1/screener/run", json={"only_buy_recommendations": True})
    assert resp.status_code == 200
    data = resp.json()
    for item in data["results"]:
        assert item["verdict"] in ["STRONG BUY", "BUY"]


def test_api_recommend_by_price():
    resp = client.get("/api/v1/screener/recommend-by-price?max_price=5000&only_buy=false&limit=5")
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0
    assert len(recs) <= 5
    for r in recs:
        assert r["current_price"] <= 5000.0
        assert "recommendation_reason" in r
        assert len(r["recommendation_reason"]) > 0


def test_api_price_tiers():
    resp = client.get("/api/v1/screener/price-tiers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_recommendations"] > 0
    assert len(data["tiers"]) == 3
    tier_ids = [t["tier_id"] for t in data["tiers"]]
    assert "budget" in tier_ids
    assert "mid_range" in tier_ids
    assert "premium" in tier_ids


def test_screener_service_direct_unit():
    emiten_service = EmitenService()
    screener_svc = ScreenerService(emiten_service)
    
    # Test price filtering
    crit = ScreenerCriteria(min_price=2000.0, max_price=6000.0)
    resp = screener_svc.run_screener(crit)
    assert resp.total_matched > 0
    for it in resp.results:
        assert 2000.0 <= it.current_price <= 6000.0
        
    # Test recommendation rationale builder
    recs = screener_svc.get_recommendations_by_price(max_price=5000.0, min_score=50.0, limit=3)
    assert len(recs) > 0
    assert all(r.recommendation_reason for r in recs)
    assert all(r.eps > 0 for r in recs)
    assert all(r.revenue > 0 for r in recs)
