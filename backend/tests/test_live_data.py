"""
Tests for Live Market Data Features:
- Real-Time News & Sentiment Engine
- Corporate Catalysts (Earnings & Dividends)
- Live WebSocket Quote Streaming
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.main import app
from app.services.news_service import NewsService
from app.models.news import NewsSentiment


@pytest.fixture
def client():
    return TestClient(app)


def test_news_sentiment_analysis():
    svc = NewsService()
    # Bullish title
    s_bull, tags_bull = svc._analyze_sentiment_and_tags("Laba Bersih BBRI Naik 15% Tembus Rekor Baru, Tebar Dividen Jumbo")
    assert s_bull == NewsSentiment.BULLISH
    assert "Dividen" in tags_bull or "Laporan Keuangan" in tags_bull

    # Bearish title
    s_bear, tags_bear = svc._analyze_sentiment_and_tags("Saham GOTO Anjlok Merosot Akibat Tekanan Rugi Kuartal Ini")
    assert s_bear == NewsSentiment.BEARISH
    assert "Laporan Keuangan" in tags_bear

    # Neutral title
    s_neu, tags_neu = svc._analyze_sentiment_and_tags("Bursa Efek Indonesia Jadwalkan Perdagangan Saham Pekan Depan")
    assert s_neu == NewsSentiment.NEUTRAL


def test_news_rss_mock(monkeypatch):
    svc = NewsService(cache_ttl_seconds=60)
    mock_rss_items = [
        {
            "title": "BBRI Catat Laba Bersih Menguat dan Siap Tebar Dividen - Bisnis.com",
            "link": "https://example.com/bbri-1",
            "pub_date": "Wed, 16 Sep 2026 10:00:00 GMT",
            "source": "Bisnis.com"
        },
        {
            "title": "IHSG Tertekan, Saham Perbankan Alami Koreksi Waspada - KONTAN",
            "link": "https://example.com/bbri-2",
            "pub_date": "Tue, 15 Sep 2026 09:00:00 GMT",
            "source": "KONTAN"
        }
    ]
    monkeypatch.setattr(svc, "_fetch_rss", lambda url: mock_rss_items)

    resp = svc.get_ticker_news("BBRI", max_items=5)
    assert resp.query_ticker == "BBRI"
    assert resp.total_items == 2
    assert resp.sentiment_summary.bullish_count == 1
    assert resp.sentiment_summary.bearish_count == 1
    assert len(resp.news) == 2


def test_api_news_endpoints(client, monkeypatch):
    mock_rss_items = [
        {
            "title": "Laba BBCA Melonjak Didukung Pertumbuhan Kredit Solid - CNBC Indonesia",
            "link": "https://example.com/bbca-1",
            "pub_date": "Thu, 17 Sep 2026 08:00:00 GMT",
            "source": "CNBC Indonesia"
        }
    ]
    from app.api.v1 import news
    monkeypatch.setattr(news._news_service, "_fetch_rss", lambda url: mock_rss_items)

    resp = client.get("/api/v1/news/ticker/BBCA?max_items=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_ticker"] == "BBCA"
    assert data["total_items"] >= 1
    assert data["news"][0]["source"] == "CNBC Indonesia"

    # Market news
    resp_m = client.get("/api/v1/news/market?max_items=5")
    assert resp_m.status_code == 200
    data_m = resp_m.json()
    assert data_m["query_ticker"] == "IHSG"


def test_corporate_catalysts_endpoint(client, monkeypatch):
    from app.services.calendar_service import CalendarService

    mock_catalysts = {
        "ticker": "BBRI",
        "earnings_date": "2026-10-29",
        "earnings_est_avg": 94.0,
        "revenue_est_avg": 54000000000000.0,
        "ex_dividend_date": "2026-04-21",
        "recent_dividends": [{"date": "2026-04-21", "amount_per_share": 209.0}],
        "events": [
            {
                "category": "EARNINGS",
                "title": "Estimasi Rilis Laporan Keuangan BBRI",
                "date": "2026-10-29",
                "details": "EPS Est: 94.0"
            }
        ]
    }

    with patch.object(CalendarService, "get_corporate_catalysts", return_value=mock_catalysts):
        resp = client.get("/api/v1/calendar/corporate/BBRI")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "BBRI"
        assert data["earnings_date"] == "2026-10-29"
        assert data["ex_dividend_date"] == "2026-04-21"
        assert len(data["events"]) == 1


def test_websocket_live_quotes(client):
    with client.websocket_connect("/ws/live-quotes") as ws:
        # Initial status frame
        init_frame = ws.receive_json()
        assert init_frame["type"] == "connection_status"
        assert init_frame["status"] == "CONNECTED"

        # Ping
        ws.send_json({"action": "ping"})
        pong_frame = ws.receive_json()
        assert pong_frame["type"] == "pong"

        # Subscribe
        ws.send_json({"action": "subscribe", "tickers": ["BBRI"]})
        quote_frame = ws.receive_json()
        assert quote_frame["type"] == "quote_tick"
        assert quote_frame["ticker"] == "BBRI"
        assert "price" in quote_frame
        assert "timestamp" in quote_frame

        # Unsubscribe
        ws.send_json({"action": "unsubscribe", "tickers": ["BBRI"]})
        unsub_frame = ws.receive_json()
        assert unsub_frame["type"] == "unsubscribed"
        assert "BBRI" in unsub_frame["tickers"]
