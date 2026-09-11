"""
Unit and Integration Tests for Economic Calendar Agendas, Impacted Stocks Engine, FRED API, and BPS Open Data.
"""

from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.calendar_service import CalendarService
from app.models.calendar import ImpactLevel, MarketScope, EventCategory

client = TestClient(app)


def test_calendar_service_unit_basic():
    service = CalendarService()
    ref_date = date(2026, 8, 27)
    resp = service.get_calendar_agendas(reference_date=ref_date)

    assert resp.stats.total_events >= 10
    assert resp.stats.high_impact_count >= 5
    assert resp.stats.domestic_count >= 4
    assert resp.stats.us_global_count >= 4
    assert resp.stats.total_affected_stocks >= 10

    # Ensure agendas are returned
    assert len(resp.agendas) >= 10
    # Ensure upcoming highlights are present
    assert len(resp.upcoming_highlights) >= 1

    # Check that each agenda has valid impacted stocks and scenarios
    for item in resp.agendas:
        assert item.id != ""
        assert item.title != ""
        assert item.country != ""
        assert len(item.impacted_stocks) >= 1
        assert len(item.scenarios) >= 1
        assert item.transmission_mechanism != ""
        assert item.actionable_strategy != ""


def test_calendar_service_fred_and_bps_integration():
    service = CalendarService(fred_api_key="demo_key", bps_api_key="demo_key")
    # Verify FRED helper is callable
    assert hasattr(service, "_fetch_fred_series")
    assert hasattr(service, "_fetch_bps_inflation_gdp")


def test_calendar_service_scope_filter():
    service = CalendarService()
    ref_date = date(2026, 8, 27)

    # 1. Filter Indonesia only
    resp_id = service.get_calendar_agendas(scope="INDONESIA", reference_date=ref_date)
    assert len(resp_id.agendas) > 0
    for item in resp_id.agendas:
        assert item.market_scope == MarketScope.INDONESIA

    # 2. Filter US & Global only
    resp_us = service.get_calendar_agendas(scope="US_GLOBAL", reference_date=ref_date)
    assert len(resp_us.agendas) > 0
    for item in resp_us.agendas:
        assert item.market_scope == MarketScope.US_GLOBAL


def test_calendar_service_category_filter():
    service = CalendarService()
    ref_date = date(2026, 8, 27)

    resp_rate = service.get_calendar_agendas(category="INTEREST_RATE", reference_date=ref_date)
    assert len(resp_rate.agendas) >= 2
    for item in resp_rate.agendas:
        assert item.category == EventCategory.INTEREST_RATE


def test_calendar_service_ticker_filter():
    service = CalendarService()
    ref_date = date(2026, 8, 27)

    # Filter events affecting BBRI
    resp_bbri = service.get_calendar_agendas(ticker="BBRI", reference_date=ref_date)
    assert len(resp_bbri.agendas) >= 2
    for item in resp_bbri.agendas:
        tickers = [s.ticker for s in item.impacted_stocks]
        assert "BBRI" in tickers


def test_calendar_service_search():
    service = CalendarService()
    ref_date = date(2026, 8, 27)

    # Search for 'FOMC'
    resp_fomc = service.get_calendar_agendas(search="FOMC", reference_date=ref_date)
    assert len(resp_fomc.agendas) >= 1
    assert any("FOMC" in a.title.upper() for a in resp_fomc.agendas)

    # Search for 'Minyak'
    resp_oil = service.get_calendar_agendas(search="Minyak", reference_date=ref_date)
    assert len(resp_oil.agendas) >= 1


def test_calendar_service_sector_sensitivities():
    service = CalendarService()
    matrix = service.get_sector_sensitivities()
    assert len(matrix) >= 5
    assert any(m.sector_name.startswith("Perbankan") for m in matrix)
    assert any(m.sector_name.startswith("Pertambangan") for m in matrix)


def test_api_get_calendar():
    resp = client.get("/api/v1/calendar")
    assert resp.status_code == 200
    data = resp.json()

    assert "stats" in data
    assert "agendas" in data
    assert "upcoming_highlights" in data
    assert "sector_sensitivities" in data
    assert data["stats"]["total_events"] >= 10
    assert len(data["agendas"]) >= 10


def test_api_get_calendar_with_params():
    resp = client.get("/api/v1/calendar?scope=INDONESIA&impact_level=HIGH")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["agendas"]) >= 1
    for a in data["agendas"]:
        assert a["market_scope"] == "INDONESIA"
        assert a["impact_level"] == "HIGH"


def test_api_get_agenda_detail():
    # 1. Valid ID
    resp = client.get("/api/v1/calendar/bi-rate-decision")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "bi-rate-decision"
    assert "impacted_stocks" in data
    assert len(data["impacted_stocks"]) >= 1
    assert "scenarios" in data

    # 2. Invalid ID -> 404
    resp_404 = client.get("/api/v1/calendar/non-existent-agenda-xyz")
    assert resp_404.status_code == 404


def test_api_get_sector_sensitivity():
    resp = client.get("/api/v1/calendar/sectors/sensitivity")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    assert "sector_name" in data[0]
    assert "key_tickers" in data[0]
