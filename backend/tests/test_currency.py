"""
Unit & Integration Tests for Currency Exchange Rates & Conversions via Bank Indonesia JISDOR.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.services.currency_service import CurrencyService

client = TestClient(app)


def test_currency_service_live_rate():
    svc = CurrencyService()
    rate_info = svc.get_live_rate(force_refresh=True)
    assert rate_info.base_currency == "USD"
    assert rate_info.target_currency == "IDR"
    assert rate_info.usd_to_idr > 5000
    assert rate_info.idr_to_usd > 0
    assert "1 USD = Rp" in rate_info.formatted_rate
    assert "Bank Indonesia" in rate_info.source or "JISDOR" in rate_info.source


def test_currency_service_conversion():
    svc = CurrencyService()
    # Convert 10,000,000 IDR to USD
    conv_idr_to_usd = svc.convert(amount=10_000_000, from_currency="IDR", to_currency="USD")
    assert conv_idr_to_usd.from_currency == "IDR"
    assert conv_idr_to_usd.to_currency == "USD"
    assert conv_idr_to_usd.converted_amount > 0
    assert conv_idr_to_usd.formatted_original == "Rp 10,000,000"
    assert "$" in conv_idr_to_usd.formatted_converted

    # Convert 1,000 USD to IDR
    conv_usd_to_idr = svc.convert(amount=1_000, from_currency="USD", to_currency="IDR")
    assert conv_usd_to_idr.from_currency == "USD"
    assert conv_usd_to_idr.to_currency == "IDR"
    assert conv_usd_to_idr.converted_amount > 5_000_000
    assert conv_usd_to_idr.formatted_original == "$1,000.00"
    assert "Rp" in conv_usd_to_idr.formatted_converted


def test_api_currency_rate_endpoint():
    resp = client.get("/api/v1/currency/rate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_currency"] == "USD"
    assert data["target_currency"] == "IDR"
    assert data["usd_to_idr"] > 5000
    assert data["idr_to_usd"] > 0
    assert "last_updated" in data
    assert "formatted_rate" in data
    assert "source" in data
    assert "Bank Indonesia" in data["source"] or "JISDOR" in data["source"]


def test_api_currency_convert_get_endpoint():
    resp = client.get("/api/v1/currency/convert?amount=5000000&from_currency=IDR&to_currency=USD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount"] == 5000000
    assert data["from_currency"] == "IDR"
    assert data["to_currency"] == "USD"
    assert data["converted_amount"] > 0
    assert "$" in data["formatted_converted"]


def test_api_currency_convert_post_endpoint():
    payload = {
        "amount": 250.0,
        "from_currency": "USD",
        "to_currency": "IDR"
    }
    resp = client.post("/api/v1/currency/convert", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount"] == 250.0
    assert data["from_currency"] == "USD"
    assert data["to_currency"] == "IDR"
    assert data["converted_amount"] > 1_000_000
    assert "Rp" in data["formatted_converted"]
