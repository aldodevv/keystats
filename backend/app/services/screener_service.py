"""
Screener Service: Multi-emiten filtering, custom ratio filtering, price-based recommendation, and preset strategies.
"""

from typing import List, Optional, Dict
import datetime
from app.services.emiten_service import EmitenService
from app.models.screener import (
    ScreenerCriteria,
    ScreenerPreset,
    ScreenerResponse,
    EmitenSummaryItem,
    PriceRecommendationItem,
    PriceTierGroup,
    PriceTierRecommendationResponse
)
from app.models.score import EmitenAnalysisReport, VerdictAction


class ScreenerService:
    def __init__(self, emiten_service: EmitenService):
        self.emiten_service = emiten_service

    def run_screener(self, criteria: Optional[ScreenerCriteria] = None) -> ScreenerResponse:
        criteria = criteria or ScreenerCriteria()
        
        # If preset is selected, apply preset thresholds
        if criteria.preset and criteria.preset != ScreenerPreset.CUSTOM:
            criteria = self._apply_preset(criteria.preset, criteria)
            
        all_tickers = self.emiten_service.list_all_available_tickers()
        matched: List[EmitenSummaryItem] = []
        
        for report in self.emiten_service.analyze_many(all_tickers):
            if self._matches_criteria(report, criteria):
                item = EmitenSummaryItem(
                    ticker=report.ticker,
                    name=report.name,
                    sector=report.sector,
                    current_price=report.current_price,
                    market_cap=report.market_cap,
                    eps=report.eps,
                    revenue=report.revenue,
                    revenue_growth=report.growth.revenue_growth_yoy,
                    eps_growth=report.growth.eps_growth_yoy,
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
                matched.append(item)
                
        # Sort matched results based on criteria.sort_by
        sort_by = criteria.sort_by or "composite_score"
        if sort_by == "price_asc":
            matched.sort(key=lambda x: x.current_price)
        elif sort_by == "price_desc":
            matched.sort(key=lambda x: x.current_price, reverse=True)
        elif sort_by == "upside_pct":
            matched.sort(key=lambda x: x.upside_pct, reverse=True)
        elif sort_by == "dividend_yield":
            matched.sort(key=lambda x: x.dividend_yield, reverse=True)
        elif sort_by == "roe":
            matched.sort(key=lambda x: x.roe, reverse=True)
        else:
            matched.sort(key=lambda x: x.composite_score, reverse=True)
        
        return ScreenerResponse(
            total_matched=len(matched),
            results=matched,
            applied_preset=criteria.preset.value if criteria.preset else None
        )

    def get_recommendations_by_price(
        self,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_score: float = 60.0,
        only_buy: bool = True,
        sector: Optional[str] = None,
        sort_by: str = "composite_score",
        limit: int = 10
    ) -> List[PriceRecommendationItem]:
        """Search and rank top recommended stocks within a specific price budget."""
        criteria = ScreenerCriteria(
            min_price=min_price,
            max_price=max_price,
            min_composite_score=min_score,
            only_buy_recommendations=only_buy,
            sectors=[sector] if sector else None,
            sort_by=sort_by
        )
        
        all_tickers = self.emiten_service.list_all_available_tickers()
        recommendations: List[PriceRecommendationItem] = []
        
        for report in self.emiten_service.analyze_many(all_tickers):
            if self._matches_criteria(report, criteria):
                reason = self._build_recommendation_reason(report)
                recommendations.append(
                    PriceRecommendationItem(
                        ticker=report.ticker,
                        name=report.name,
                        sector=report.sector,
                        current_price=report.current_price,
                        eps=report.eps,
                        revenue=report.revenue,
                        eps_growth=report.growth.eps_growth_yoy,
                        composite_score=report.composite_score,
                        grade=report.grade,
                        verdict=report.verdict.value,
                        upside_pct=report.valuation.upside_downside_pct,
                        per=report.valuation.per,
                        pbv=report.valuation.pbv,
                        roe=report.profitability.roe,
                        dividend_yield=report.cash_flow_dividend.dividend_yield,
                        recommendation_reason=reason
                    )
                )
                
        # Sort recommendations
        if sort_by == "price_asc":
            recommendations.sort(key=lambda x: x.current_price)
        elif sort_by == "price_desc":
            recommendations.sort(key=lambda x: x.current_price, reverse=True)
        elif sort_by == "upside_pct":
            recommendations.sort(key=lambda x: x.upside_pct, reverse=True)
        elif sort_by == "dividend_yield":
            recommendations.sort(key=lambda x: x.dividend_yield, reverse=True)
        elif sort_by == "roe":
            recommendations.sort(key=lambda x: x.roe, reverse=True)
        else:
            recommendations.sort(key=lambda x: x.composite_score, reverse=True)
            
        return recommendations[:limit]

    def get_price_tier_recommendations(self) -> PriceTierRecommendationResponse:
        """Returns recommendations grouped into 3 distinct price tiers (Budget, Mid-Range, Premium Bluechips)."""
        tier_definitions = [
            {
                "tier_id": "budget",
                "tier_name": "🪙 Budget Friendly Gems",
                "price_range_desc": "Harga < Rp 1.000 (Modal terjangkau dengan fundamental sehat)",
                "min_price": None,
                "max_price": 1000.0,
                "min_score": 55.0
            },
            {
                "tier_id": "mid_range",
                "tier_name": "💵 Mid-Range Quality Growth",
                "price_range_desc": "Harga Rp 1.000 - Rp 5.000 (Valuasi menarik & bertumbuh stabil)",
                "min_price": 1000.0,
                "max_price": 5000.0,
                "min_score": 60.0
            },
            {
                "tier_id": "premium",
                "tier_name": "💎 Premium Blue Chips",
                "price_range_desc": "Harga > Rp 5.000 (Market leader dengan moat kuat & dividen konsisten)",
                "min_price": 5000.0,
                "max_price": None,
                "min_score": 65.0
            }
        ]
        
        tier_groups: List[PriceTierGroup] = []
        total_recs = 0
        
        for td in tier_definitions:
            recs = self.get_recommendations_by_price(
                min_price=td["min_price"],
                max_price=td["max_price"],
                min_score=td["min_score"],
                only_buy=False,  # show top scored in this tier
                sort_by="composite_score",
                limit=5
            )
            total_recs += len(recs)
            tier_groups.append(
                PriceTierGroup(
                    tier_id=td["tier_id"],
                    tier_name=td["tier_name"],
                    price_range_desc=td["price_range_desc"],
                    min_price=td["min_price"],
                    max_price=td["max_price"],
                    count=len(recs),
                    items=recs
                )
            )
            
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return PriceTierRecommendationResponse(
            total_recommendations=total_recs,
            tiers=tier_groups,
            generated_at=now_str
        )

    def _build_recommendation_reason(self, rep: EmitenAnalysisReport) -> str:
        """Constructs a concise rationale explaining why this stock is recommended."""
        reasons = []
        if rep.valuation.upside_downside_pct > 15.0:
            reasons.append(f"Potensi upside tinggi (+{rep.valuation.upside_downside_pct:.1f}%)")
        elif rep.valuation.upside_downside_pct > 0:
            reasons.append(f"Valuasi terdiskon (Upside +{rep.valuation.upside_downside_pct:.1f}%)")
            
        if rep.profitability.roe >= 15.0:
            reasons.append(f"Profitabilitas superior (ROE {rep.profitability.roe}%)")
            
        if rep.cash_flow_dividend.dividend_yield >= 4.0:
            reasons.append(f"Yield dividen menarik ({rep.cash_flow_dividend.dividend_yield}%)")
            
        if rep.quality.piotroski_f_score >= 7:
            reasons.append(f"Kualitas keuangan prima (Piotroski {rep.quality.piotroski_f_score}/9)")
            
        if rep.solvency.der <= 0.8:
            reasons.append(f"Hutang terkendali (DER {rep.solvency.der}x)")

        if not reasons:
            reasons.append(f"Skor fundamental {rep.composite_score}/100 dengan Grade {rep.grade}")
            
        return " • ".join(reasons[:2])

    def _matches_criteria(self, rep: EmitenAnalysisReport, c: ScreenerCriteria) -> bool:
        # Sectors
        if c.sectors and rep.sector not in c.sectors:
            return False
            
        # Stock Price (Harga Saham IDR)
        if c.min_price is not None and rep.current_price < c.min_price:
            return False
        if c.max_price is not None and rep.current_price > c.max_price:
            return False
            
        # Market Cap
        if c.min_market_cap and rep.market_cap < c.min_market_cap:
            return False
        if c.max_market_cap and rep.market_cap > c.max_market_cap:
            return False
            
        # Valuation
        if c.min_pe and rep.valuation.per < c.min_pe:
            return False
        if c.max_pe and rep.valuation.per > c.max_pe:
            return False
        if c.min_pbv and rep.valuation.pbv < c.min_pbv:
            return False
        if c.max_pbv and rep.valuation.pbv > c.max_pbv:
            return False
        if c.max_peg and rep.valuation.peg_ratio is not None and rep.valuation.peg_ratio > c.max_peg:
            return False
        if c.min_upside_pct and rep.valuation.upside_downside_pct < c.min_upside_pct:
            return False
            
        # Profitability
        if c.min_roe and rep.profitability.roe < c.min_roe:
            return False
        if c.min_npm and rep.profitability.npm < c.min_npm:
            return False
        if c.min_roic and rep.profitability.roic < c.min_roic:
            return False
            
        # Solvency & Quality
        if c.max_der and rep.solvency.der > c.max_der:
            return False
        if c.min_altman_z and rep.solvency.altman_z_score < c.min_altman_z:
            return False
        if c.min_piotroski_f and rep.quality.piotroski_f_score < c.min_piotroski_f:
            return False
        if c.min_current_ratio and rep.liquidity.current_ratio < c.min_current_ratio:
            return False
            
        # Dividend & Cash Flow
        if c.min_dividend_yield and rep.cash_flow_dividend.dividend_yield < c.min_dividend_yield:
            return False
        if c.max_dpr and rep.cash_flow_dividend.dpr > c.max_dpr:
            return False
        if c.must_have_positive_fcf and rep.cash_flow_dividend.fcf <= 0:
            return False
            
        # Growth
        if c.min_revenue_growth and rep.growth.revenue_growth_yoy < c.min_revenue_growth:
            return False
        if c.min_eps_growth and rep.growth.eps_growth_yoy < c.min_eps_growth:
            return False
            
        # Composite Score & Verdicts
        if c.min_composite_score and rep.composite_score < c.min_composite_score:
            return False
            
        if c.verdicts:
            verdict_val = rep.verdict.value if hasattr(rep.verdict, "value") else str(rep.verdict)
            verdict_name = rep.verdict.name if hasattr(rep.verdict, "name") else str(rep.verdict)
            if verdict_val not in c.verdicts and verdict_name not in c.verdicts:
                return False
                
        if c.only_undervalued and rep.valuation.upside_downside_pct <= 0:
            return False
            
        if c.only_buy_recommendations:
            verdict_val = rep.verdict.value if hasattr(rep.verdict, "value") else str(rep.verdict)
            if verdict_val not in ["STRONG BUY", "BUY"]:
                return False
            
        return True

    def _apply_preset(self, preset: ScreenerPreset, existing: ScreenerCriteria) -> ScreenerCriteria:
        c = existing.model_copy()
        
        if preset == ScreenerPreset.BUFFETT_MOAT:
            c.min_roe = 14.0
            c.max_der = 1.0
            c.min_piotroski_f = 6
            c.must_have_positive_fcf = True
            c.min_composite_score = 65.0
            
        elif preset == ScreenerPreset.DIVIDEND_CASH_COW:
            c.min_dividend_yield = 4.5
            c.max_dpr = 80.0
            c.min_altman_z = 1.8
            c.must_have_positive_fcf = True
            
        elif preset == ScreenerPreset.GARP:
            c.max_peg = 1.2
            c.min_eps_growth = 8.0
            c.min_roe = 10.0
            c.min_upside_pct = 5.0
            
        elif preset == ScreenerPreset.DEEP_VALUE:
            c.max_pbv = 1.5
            c.max_pe = 12.0
            c.min_upside_pct = 15.0
            c.min_altman_z = 1.5
            
        elif preset == ScreenerPreset.MOMENTUM_QUALITY:
            c.min_eps_growth = 10.0
            c.min_revenue_growth = 6.0
            c.min_piotroski_f = 6
            c.min_composite_score = 60.0
            
        elif preset == ScreenerPreset.AFFORDABLE_GEMS:
            c.max_price = 2500.0
            c.min_composite_score = 60.0
            c.min_roe = 12.0
            c.max_der = 1.5
            c.min_piotroski_f = 5
            
        elif preset == ScreenerPreset.UNDERVALUED_DEALS:
            c.only_undervalued = True
            c.only_buy_recommendations = True
            c.min_upside_pct = 10.0
            c.min_composite_score = 65.0
            
        return c

