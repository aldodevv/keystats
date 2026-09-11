"""
Unit tests for TelegramBotService and Telegram API endpoints.
"""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.telegram_service import TelegramBotService
from app.models.market import (
    MarketSummaryResponse,
    MarketOverviewStats,
    TopPickItem
)

client = TestClient(app)


def test_telegram_status_endpoint():
    response = client.get("/api/v1/telegram/status")
    assert response.status_code == 200
    data = response.json()
    assert "configured" in data
    assert data["bot_username"] == "@TradeXQBot"


@patch("requests.post")
def test_telegram_send_test_message(mock_post):
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = {
        "ok": True,
        "result": {"message_id": 99, "chat": {"id": 7690577065}}
    }

    svc = TelegramBotService(bot_token="fake_test_token_12345", default_chat_id="7690577065")
    res = svc.send_test_message()
    assert res["success"] is True
    assert res["result"]["message_id"] == 99


def test_format_daily_picks_html():
    svc = TelegramBotService(bot_token="dummy_token_12345", default_chat_id="7690577065")
    mock_summary = MarketSummaryResponse(
        stats=MarketOverviewStats(
            total_emitens=10,
            undervalued_count=6,
            overvalued_count=2,
            fair_count=2,
            avg_composite_score=75.0,
            avg_per=12.0,
            avg_pbv=1.5,
            avg_roe=18.0,
            avg_dividend_yield=4.5,
            top_sector="Financials",
            top_sector_count=4
        ),
        top_picks=[
            TopPickItem(
                ticker="BBRI",
                name="Bank Rakyat Indonesia",
                sector="Financials",
                category="TOP_PICK_OVERALL",
                category_title="🌟 Rekomendasi Utama Esok Hari",
                category_tag="TOP ALPHA",
                badge_color="emerald",
                current_price=4800,
                fair_value=5500,
                upside_pct=14.6,
                composite_score=85.0,
                grade="A",
                verdict="BUY",
                per=11.5,
                pbv=2.1,
                roe=19.5,
                piotroski_f_score=8,
                altman_z_score=2.8,
                dividend_yield=5.2,
                key_metrics_summary=["ROE: 19.5%"],
                rationale=["Neraca kuat"],
                catalyst="Pertumbuhan kredit mikro prima.",
                entry_zone="Rp4,750 - Rp4,800",
                take_profit_1=5500,
                take_profit_2=6000,
                stop_loss=4500,
                risk_to_reward_ratio=3.5,
                buy_zone_label="STRONG ACCUMULATION",
                max_allocation_pct=15.0
            )
        ],
        emitens=[],
        generated_at_desc="Test Summary"
    )

    html = svc.format_daily_picks_html(mock_summary)
    assert "BBRI" in html
    assert "Bank Rakyat Indonesia" in html
    assert "Area Beli (Entry)" in html
    assert "Target Profit 1" in html
    assert "Stop Loss (SL)" in html
    assert "F-Score 8/9" in html
    assert "@TradeXQBot" in html
