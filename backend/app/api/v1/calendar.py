"""
FastAPI Router for Economic and Market Calendar Agendas & Impacted Stocks Engine.
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException

from app.models.calendar import (
    CalendarResponse,
    CalendarAgendaItem,
    SectorSensitivityItem
)
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["Market Calendar & Macro Catalysts"])
calendar_service = CalendarService()


@router.get("", response_model=CalendarResponse)
def get_calendar_agendas(
    scope: Optional[str] = Query(None, description="Scope filter: ALL, INDONESIA, US_GLOBAL"),
    category: Optional[str] = Query(None, description="Category: ALL, INTEREST_RATE, INFLATION_GDP, COMMODITY_ENERGY, DIVIDEND, CORPORATE_ACTION, INDEX_REBALANCE, TRADE_MACRO"),
    impact_level: Optional[str] = Query(None, description="Impact level: ALL, HIGH, MEDIUM, LOW"),
    timeframe: Optional[str] = Query(None, description="Timeframe: ALL, TODAY, THIS_WEEK, THIS_MONTH, UPCOMING"),
    search: Optional[str] = Query(None, description="Search query across title, description, country, or ticker"),
    ticker: Optional[str] = Query(None, description="Filter agendas affecting a specific IDX ticker (e.g. BBRI, ADRO, GOTO)")
):
    """
    Returns macroeconomic and corporate calendar events affecting Indonesian stocks (IDX),
    including US & global agendas, detailed transmission mechanisms, impacted tickers, and scenario analyses.
    """
    return calendar_service.get_calendar_agendas(
        scope=scope,
        category=category,
        impact_level=impact_level,
        timeframe=timeframe,
        search=search,
        ticker=ticker
    )


@router.get("/sectors/sensitivity", response_model=List[SectorSensitivityItem])
def get_sector_sensitivities():
    """
    Returns the sensitivity matrix of IDX sectors against key macroeconomic catalysts.
    """
    return calendar_service.get_sector_sensitivities()


@router.get("/{agenda_id}", response_model=CalendarAgendaItem)
def get_agenda_detail(agenda_id: str):
    """
    Returns comprehensive details of a single calendar event including scenarios and impacted stocks.
    """
    item = calendar_service.get_agenda_by_id(agenda_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Agenda with id '{agenda_id}' not found")
    return item
