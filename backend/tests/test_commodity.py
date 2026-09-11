"""
Unit & Integration Tests for Commodities, Forex, and Scoped Emiten Fundamental Evaluation.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.services.commodity_service import CommodityService
from app.models.commodity import CommodityCategory, InvestmentSuitability

client = TestClient(app)


def test_commodity_service_macro_overview():
    svc = CommodityService()
    res = svc.get_macro_overview(force_refresh=True)

    assert res.total_commodities > 5
    assert res.total_forex_pairs >= 5
    assert len(res.commodities) == res.total_commodities
    assert len(res.forex_pairs) == res.total_forex_pairs

    # Verify key commodities exist
    comm_ids = {c.id for c in res.commodities}
    assert "GOLD" in comm_ids
    assert "COAL" in comm_ids
    assert "BRENT_OIL" in comm_ids
    assert "CPO" in comm_ids
    assert "NICKEL" in comm_ids
    assert "COPPER" in comm_ids

    # Verify key forex pairs exist
    forex_ids = {f.id for f in res.forex_pairs}
    assert "USD_IDR" in forex_ids
    assert "DXY" in forex_ids
    assert "EUR_IDR" in forex_ids

    # Check non-empty real-time fields
    gold = next(c for c in res.commodities if c.id == "GOLD")
    assert gold.price > 1000.0
    assert gold.previous_close > 1000.0
    assert gold.unit == "USD/troy oz"
    assert gold.currency == "USD"
    assert gold.related_emitens_count > 0

    usd_idr = next(f for f in res.forex_pairs if f.id == "USD_IDR")
    assert usd_idr.price > 10000.0


def test_commodity_scoped_emitens_coal():
    svc = CommodityService()
    res = svc.get_commodity_scoped_emitens("COAL")

    assert res is not None
    assert res.commodity.id == "COAL"
    assert res.total_related_emitens >= 5
    assert len(res.emitens) == res.total_related_emitens

    # Verify ADRO and PTBA are in the list
    tickers = {e.ticker for e in res.emitens}
    assert "ADRO" in tickers
    assert "PTBA" in tickers
    assert "ITMG" in tickers

    # Check fundamental fields
    adro = next(e for e in res.emitens if e.ticker == "ADRO")
    assert adro.composite_score > 0
    assert adro.current_price > 0
    assert adro.fair_value > 0
    assert adro.roe != 0.0
    assert adro.impact_direction == "POSITIF / UNTUNG"
    assert len(adro.correlation_thesis) > 10
    assert adro.suitability in [
        InvestmentSuitability.SANGAT_LAYAK,
        InvestmentSuitability.LAYAK_ANALISIS,
        InvestmentSuitability.NETRAL,
        InvestmentSuitability.SPEKULATIF_WASPADA,
    ]


def test_commodity_scoped_emitens_gold():
    svc = CommodityService()
    res = svc.get_commodity_scoped_emitens("GOLD")

    assert res is not None
    assert res.commodity.id == "GOLD"
    tickers = {e.ticker for e in res.emitens}
    assert "ANTM" in tickers
    assert "MDKA" in tickers


def test_commodity_scoped_emitens_forex_usd_idr():
    svc = CommodityService()
    res = svc.get_commodity_scoped_emitens("USD_IDR")

    assert res is not None
    assert res.commodity.id == "USD_IDR"
    tickers = {e.ticker for e in res.emitens}
    assert "ADRO" in tickers  # Exporter
    assert "ICBP" in tickers  # Importer/debtor

    icbp = next(e for e in res.emitens if e.ticker == "ICBP")
    assert icbp.impact_direction == "NEGATIF / BEBAN BIAYA"


def test_api_commodities_overview():
    resp = client.get("/api/v1/commodities/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "commodities" in data
    assert "forex_pairs" in data
    assert "top_gainers" in data
    assert data["total_commodities"] > 0
    assert data["total_forex_pairs"] > 0


def test_api_commodities_scoped_emitens():
    resp = client.get("/api/v1/commodities/COAL/emitens")
    assert resp.status_code == 200
    data = resp.json()
    assert data["commodity"]["id"] == "COAL"
    assert data["total_related_emitens"] > 0
    assert len(data["emitens"]) > 0

    first_emiten = data["emitens"][0]
    assert "ticker" in first_emiten
    assert "composite_score" in first_emiten
    assert "grade" in first_emiten
    assert "upside_pct" in first_emiten
    assert "suitability" in first_emiten
    assert "suitability_label" in first_emiten
    assert "correlation_thesis" in first_emiten


def test_api_commodities_not_found():
    resp = client.get("/api/v1/commodities/UNKNOWN_SYMBOL_XYZ/emitens")
    assert resp.status_code == 404
