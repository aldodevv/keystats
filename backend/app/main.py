"""
Main FastAPI Application Entrypoint for BRIGHTS — BRI Stock Intelligence.
"""

# Load .env before any router/service imports so providers see configured API keys.
import app.config  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api.v1.emiten import router as emiten_router
from app.api.v1.compare import router as compare_router
from app.api.v1.screener import router as screener_router
from app.api.v1.market import router as market_router
from app.api.v1.currency import router as currency_router
from app.api.v1.chart import router as chart_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.commodity import router as commodity_router

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title="BRIGHTS — BRI Stock Intelligence API",
    description="BRIGHTS (BRI Stock Intelligence): Fundamental Analysis, Multi-Model Valuation, Shareholder Insight, and Scoring API for Indonesian Stock Exchange (IDX) emitens.",
    version="1.0.0"
)

# Enable GZip compression for API responses & static assets
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Enable CORS for Next.js / Web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 routers
app.include_router(market_router, prefix="/api/v1")
app.include_router(commodity_router, prefix="/api/v1")
app.include_router(currency_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(emiten_router, prefix="/api/v1")
app.include_router(compare_router, prefix="/api/v1")
app.include_router(screener_router, prefix="/api/v1")
app.include_router(chart_router, prefix="/api/v1")
app.include_router(telegram_router, prefix="/api/v1")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "brights-stock-intelligence", "version": "1.0.0"}


@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "Welcome to BRIGHTS — BRI Stock Intelligence API",
        "docs": "/docs"
    }


@app.api_route("/stock/{ticker}", methods=["GET", "HEAD"])
def serve_stock_page(ticker: str):
    """
    Direct permalink for single emiten analysis (e.g. /stock/BBRI, /stock/BBCA).
    Serves the SPA index.html so the frontend can load the full report dynamically.
    """
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": f"Stock analysis for {ticker.upper()}",
        "docs": "/docs"
    }
