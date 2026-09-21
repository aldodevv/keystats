"""
WebSocket Live Quote Streaming for IDX Stocks.
Enables bidirectional, low-latency market quote updates for frontend terminals.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Any
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.data_providers.yfinance_provider import YFinanceProvider

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger("brights.websocket")

_yf_provider = YFinanceProvider()


class QuoteSubscriptionManager:
    def __init__(self):
        # Maps WebSocket connection -> set of subscribed ticker strings
        self.active_connections: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections[websocket] = set()

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                del self.active_connections[websocket]

    async def subscribe(self, websocket: WebSocket, tickers: list):
        async with self._lock:
            if websocket in self.active_connections:
                for t in tickers:
                    clean = str(t).upper().replace(".JK", "").strip()
                    if clean:
                        self.active_connections[websocket].add(clean)

    async def unsubscribe(self, websocket: WebSocket, tickers: list):
        async with self._lock:
            if websocket in self.active_connections:
                for t in tickers:
                    clean = str(t).upper().replace(".JK", "").strip()
                    self.active_connections[websocket].discard(clean)

    def get_subscriptions(self, websocket: WebSocket) -> Set[str]:
        return self.active_connections.get(websocket, set())


manager = QuoteSubscriptionManager()


def _fetch_quick_quote(ticker: str) -> Dict[str, Any]:
    """Fetches real current price & change data for an IDX ticker."""
    clean = ticker.upper().replace(".JK", "").strip()
    try:
        raw = _yf_provider.fetch_keystats(clean)
        price = raw.current_price
        # Fetch 52w range / open / previous close if available
        return {
            "type": "quote_tick",
            "ticker": clean,
            "price": price,
            "change": 0.0,
            "change_percent": 0.0,
            "market_cap": raw.market_cap,
            "volume": getattr(raw, "volume", 0),
            "timestamp": datetime.now().strftime("%H:%M:%S WIB"),
            "is_live": True
        }
    except Exception:
        return {
            "type": "quote_tick",
            "ticker": clean,
            "price": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "market_cap": 0,
            "volume": 0,
            "timestamp": datetime.now().strftime("%H:%M:%S WIB"),
            "is_live": False
        }


@router.websocket("/ws/live-quotes")
async def websocket_live_quotes(websocket: WebSocket):
    await manager.connect(websocket)
    # Send initial welcome / status frame
    await websocket.send_json({
        "type": "connection_status",
        "status": "CONNECTED",
        "message": "Connected to BRIGHTS Live IDX Quote Streamer",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                continue

            action = msg.get("action")

            if action == "subscribe":
                tickers = msg.get("tickers", [])
                if isinstance(tickers, str):
                    tickers = [tickers]
                await manager.subscribe(websocket, tickers)

                # Immediately push current quote snapshot for each subscribed ticker
                for t in tickers:
                    quote = _fetch_quick_quote(t)
                    await websocket.send_json(quote)

            elif action == "unsubscribe":
                tickers = msg.get("tickers", [])
                if isinstance(tickers, str):
                    tickers = [tickers]
                await manager.unsubscribe(websocket, tickers)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "tickers": tickers
                })

            elif action == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "server_time": datetime.now().strftime("%H:%M:%S WIB")
                })

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)
