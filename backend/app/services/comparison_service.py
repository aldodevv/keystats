"""
Comparison Service: Side-by-side peer comparison and benchmark analysis for multiple emitens.
"""

from typing import List, Dict, Any
from app.services.emiten_service import EmitenService
from app.models.screener import ComparisonResponse, EmitenSummaryItem


class ComparisonService:
    def __init__(self, emiten_service: EmitenService):
        self.emiten_service = emiten_service

    def compare_emitens(self, tickers: List[str]) -> ComparisonResponse:
        clean_tickers = [t.upper().replace(".JK", "").strip() for t in tickers if t.strip()]
        
        summary_items: List[EmitenSummaryItem] = []
        detailed_reports: List[Dict[str, Any]] = []
        
        for t in clean_tickers:
            report = self.emiten_service.analyze_single_emiten(t)
            if not report:
                continue
                
            summary = EmitenSummaryItem(
                ticker=report.ticker,
                name=report.name,
                sector=report.sector,
                current_price=report.current_price,
                market_cap=report.market_cap,
                per=report.valuation.per,
                pbv=report.valuation.pbv,
                roe=report.profitability.roe,
                der=report.solvency.der,
                piotroski_f_score=report.quality.piotroski_f_score,
                altman_z_score=report.solvency.altman_z_score,
                dividend_yield=report.cash_flow_dividend.dividend_yield,
                composite_score=report.composite_score,
                grade=report.grade,
                verdict=report.verdict.value,
                upside_pct=report.valuation.upside_downside_pct
            )
            summary_items.append(summary)
            detailed_reports.append(report.model_dump())
            
        # Determine best in class
        best_in_class = self._calculate_best_in_class(summary_items)
        
        return ComparisonResponse(
            tickers=[s.ticker for s in summary_items],
            items=summary_items,
            detailed_reports=detailed_reports,
            best_in_class=best_in_class
        )

    def _calculate_best_in_class(self, items: List[EmitenSummaryItem]) -> Dict[str, str]:
        if not items:
            return {}
            
        best = {}
        
        # Lowest PER (among positive PER)
        pos_pe = [it for it in items if it.per > 0]
        if pos_pe:
            best["cheapest_pe"] = min(pos_pe, key=lambda x: x.per).ticker
            
        # Lowest PBV (among positive PBV)
        pos_pbv = [it for it in items if it.pbv > 0]
        if pos_pbv:
            best["cheapest_pbv"] = min(pos_pbv, key=lambda x: x.pbv).ticker
            
        # Highest ROE
        best["highest_roe"] = max(items, key=lambda x: x.roe).ticker
        
        # Highest Dividend Yield
        best["highest_dividend_yield"] = max(items, key=lambda x: x.dividend_yield).ticker
        
        # Best Piotroski F-Score
        best["highest_piotroski_f"] = max(items, key=lambda x: x.piotroski_f_score).ticker
        
        # Safest Altman Z
        best["safest_altman_z"] = max(items, key=lambda x: x.altman_z_score).ticker
        
        # Highest Composite Score
        best["overall_champion"] = max(items, key=lambda x: x.composite_score).ticker
        
        return best
