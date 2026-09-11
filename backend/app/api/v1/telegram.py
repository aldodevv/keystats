"""
API Endpoints for Telegram Bot Integration:
Broadcast daily stock picks, test bot connection, and check configuration.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from app.services.telegram_service import TelegramBotService

router = APIRouter(prefix="/telegram", tags=["Telegram Bot"])
telegram_service = TelegramBotService()


class BroadcastRequest(BaseModel):
    chat_id: Optional[str] = None


class TestMessageRequest(BaseModel):
    chat_id: Optional[str] = None


@router.get("/status")
def get_telegram_status():
    """Check if Telegram bot is configured and ready to send messages."""
    return {
        "configured": telegram_service.is_configured,
        "bot_username": "@TradeXQBot",
        "default_chat_id": telegram_service.default_chat_id
    }


@router.get("/test")
@router.post("/test")
def send_test_ping(chat_id: Optional[str] = Query(None)):
    """Send a test ping message to verify Telegram bot delivery."""
    if not telegram_service.is_configured:
        raise HTTPException(
            status_code=400,
            detail="TELEGRAM_BOT_TOKEN is not configured in environment or backend/.env."
        )
    res = telegram_service.send_test_message(chat_id=chat_id)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res


@router.get("/broadcast")
@router.post("/broadcast")
def broadcast_daily_recommendations(
    background_tasks: BackgroundTasks,
    chat_id: Optional[str] = Query(None),
    sync: bool = Query(False, description="Run synchronously (may take ~30s)")
):
    """
    Run multi-factor stock analysis for tomorrow and broadcast the
    actionable recommendations to the configured Telegram bot.
    By default runs via BackgroundTasks for instant <100ms response (no cron timeouts).
    """
    if not telegram_service.is_configured:
        raise HTTPException(
            status_code=400,
            detail="TELEGRAM_BOT_TOKEN is not configured in environment or backend/.env."
        )

    if sync:
        res = telegram_service.send_daily_picks(chat_id=chat_id)
        b_res = res.get("broadcast_result", {})
        if not b_res.get("success"):
            raise HTTPException(status_code=500, detail=b_res.get("error"))
        return res

    # Run in background to prevent webhook/cron-job HTTP timeout
    background_tasks.add_task(telegram_service.send_daily_picks, chat_id=chat_id)
    return {
        "status": "queued",
        "success": True,
        "message": "Kalkulasi multi-faktor sedang diproses di background dan akan langsung dikirim ke Telegram begitu selesai (~30 detik)."
    }


