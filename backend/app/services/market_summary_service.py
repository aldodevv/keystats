"""
Market Summary & Top Daily Stock Picks Service.
Aggregates all emitens, computes market-wide statistics, and selects the best stock picks for tomorrow.
"""

from typing import List, Optional, Dict, Set
from collections import Counter
import datetime

from app.services.emiten_service import EmitenService
from app.models.score import EmitenAnalysisReport
from app.models.screener import EmitenSummaryItem
from app.models.market import MarketSummaryResponse, MarketOverviewStats, TopPickItem


class MarketSummaryService:
    def __init__(self, emiten_service: EmitenService):
        self.emiten_service = emiten_service

    def get_market_summary(self) -> MarketSummaryResponse:
        tickers = self.emiten_service.list_all_available_tickers()
        # Analyze the whole universe concurrently (cached) — seconds, not minutes.
        reports: List[EmitenAnalysisReport] = self.emiten_service.analyze_many(tickers)

        # 1. Convert to EmitenSummaryItem list
        summary_items: List[EmitenSummaryItem] = []
        for rep in reports:
            summary_items.append(
                EmitenSummaryItem(
                    ticker=rep.ticker,
                    name=rep.name,
                    sector=rep.sector,
                    current_price=rep.current_price,
                    market_cap=rep.market_cap,
                    per=rep.valuation.per,
                    pbv=rep.valuation.pbv,
                    roe=rep.profitability.roe,
                    der=rep.solvency.der,
                    piotroski_f_score=rep.quality.piotroski_f_score,
                    altman_z_score=rep.solvency.altman_z_score,
                    dividend_yield=rep.cash_flow_dividend.dividend_yield,
                    composite_score=rep.composite_score,
                    grade=rep.grade,
                    verdict=rep.verdict.value,
                    upside_pct=rep.valuation.upside_downside_pct
                )
            )

        # Sort all items by composite score descending
        summary_items.sort(key=lambda x: x.composite_score, reverse=True)

        # 2. Compute Market Statistics
        total_emitens = len(reports)
        if total_emitens > 0:
            undervalued = [r for r in reports if r.valuation.upside_downside_pct > 5.0]
            overvalued = [r for r in reports if r.valuation.upside_downside_pct < -5.0]
            fair = [r for r in reports if -5.0 <= r.valuation.upside_downside_pct <= 5.0]

            avg_comp = round(sum(r.composite_score for r in reports) / total_emitens, 1)
            valid_per = [r.valuation.per for r in reports if r.valuation.per > 0]
            avg_per = round(sum(valid_per) / max(1, len(valid_per)), 1)
            valid_pbv = [r.valuation.pbv for r in reports if r.valuation.pbv > 0]
            avg_pbv = round(sum(valid_pbv) / max(1, len(valid_pbv)), 2)
            avg_roe = round(sum(r.profitability.roe for r in reports) / total_emitens, 1)
            avg_div = round(sum(r.cash_flow_dividend.dividend_yield for r in reports) / total_emitens, 1)

            sector_counts = Counter(r.sector for r in reports)
            top_sector, top_sector_count = sector_counts.most_common(1)[0] if sector_counts else ("-", 0)

            stats = MarketOverviewStats(
                total_emitens=total_emitens,
                undervalued_count=len(undervalued),
                overvalued_count=len(overvalued),
                fair_count=len(fair),
                avg_composite_score=avg_comp,
                avg_per=avg_per,
                avg_pbv=avg_pbv,
                avg_roe=avg_roe,
                avg_dividend_yield=avg_div,
                top_sector=top_sector,
                top_sector_count=top_sector_count
            )
        else:
            stats = MarketOverviewStats(
                total_emitens=0,
                undervalued_count=0,
                overvalued_count=0,
                fair_count=0,
                avg_composite_score=0.0,
                avg_per=0.0,
                avg_pbv=0.0,
                avg_roe=0.0,
                avg_dividend_yield=0.0,
                top_sector="-",
                top_sector_count=0
            )

        # 3. Select Distinct Top Picks for Tomorrow
        top_picks = self._select_top_picks(reports)

        generated_date_str = datetime.datetime.now().strftime("%d %B %Y")

        return MarketSummaryResponse(
            stats=stats,
            top_picks=top_picks,
            emitens=summary_items,
            generated_at_desc=f"Analisis Kuantitatif IDX Pasar Modal • Update {generated_date_str}"
        )

    def _select_top_picks(self, reports: List[EmitenAnalysisReport]) -> List[TopPickItem]:
        if not reports:
            return []

        used_tickers: Set[str] = set()
        picks: List[TopPickItem] = []

        # -------------------------------------------------------------
        # Pick 1: Stock of the Day (Overall Best Alpha & Health)
        # -------------------------------------------------------------
        # Criteria: Highest Composite Score with positive upside and Piotroski >= 6
        candidates_overall = [
            r for r in reports
            if r.valuation.upside_downside_pct > 0 and r.quality.piotroski_f_score >= 6
        ]
        if not candidates_overall:
            candidates_overall = sorted(reports, key=lambda x: x.composite_score, reverse=True)
        else:
            candidates_overall.sort(
                key=lambda x: (x.composite_score * 0.6 + min(x.valuation.upside_downside_pct, 40.0) * 0.4),
                reverse=True
            )

        if candidates_overall:
            best_overall = candidates_overall[0]
            used_tickers.add(best_overall.ticker)
            picks.append(self._build_top_pick_item(
                rep=best_overall,
                category="TOP_PICK_OVERALL",
                category_title="🌟 Rekomendasi Utama Esok Hari",
                category_tag="TOP ALPHA & OVERALL BEST",
                badge_color="emerald",
                catalyst=f"Kombinasi skor komposit prima ({best_overall.composite_score}/100 Grade {best_overall.grade}), potensi upside +{best_overall.valuation.upside_downside_pct:.1f}%, dan F-Score {best_overall.quality.piotroski_f_score}/9 menjadikannya pilihan investasi & swing paling optimal untuk esok hari."
            ))

        # -------------------------------------------------------------
        # Pick 2: Deep Value & High Margin of Safety
        # -------------------------------------------------------------
        # Criteria: Realistic upside % (10% to 150%), Altman Z safe (>= 1.8), Piotroski >= 5, PBV >= 0.3, Score >= 55
        candidates_value = [
            r for r in reports
            if r.ticker not in used_tickers
            and 10.0 < r.valuation.upside_downside_pct <= 150.0
            and r.solvency.altman_z_score >= 1.8
            and r.quality.piotroski_f_score >= 5
            and r.valuation.pbv >= 0.3
            and r.composite_score >= 55.0
        ]
        candidates_value.sort(key=lambda x: x.valuation.upside_downside_pct, reverse=True)

        if candidates_value:
            best_val = candidates_value[0]
            used_tickers.add(best_val.ticker)
            picks.append(self._build_top_pick_item(
                rep=best_val,
                category="BEST_VALUE",
                category_title="💎 Best Value & Margin of Safety",
                category_tag="UNDERVALUED BARGAIN",
                badge_color="cyan",
                catalyst=f"Valuasi terdiskon signifikan dari nilai wajar (Upside +{best_val.valuation.upside_downside_pct:.1f}% ke Rp{best_val.valuation.average_fair_value:,.0f}) dengan neraca kuat (Altman Z {best_val.solvency.altman_z_score:.2f}) meminimalkan downside risk."
            ))

        # -------------------------------------------------------------
        # Pick 3: Quality & Economic Moat
        # -------------------------------------------------------------
        # Criteria: Highest ROE & Piotroski (7-9) with healthy score & reasonable valuation
        candidates_quality = [
            r for r in reports
            if r.ticker not in used_tickers
            and r.profitability.roe >= 15.0
            and r.quality.piotroski_f_score >= 6
            and r.composite_score >= 60.0
            and r.valuation.upside_downside_pct >= -15.0
        ]
        candidates_quality.sort(
            key=lambda x: (x.profitability.roe * 0.6 + x.quality.piotroski_f_score * 5.0 + x.composite_score * 0.4),
            reverse=True
        )

        if candidates_quality:
            best_qual = candidates_quality[0]
            used_tickers.add(best_qual.ticker)
            picks.append(self._build_top_pick_item(
                rep=best_qual,
                category="HIGH_QUALITY_MOAT",
                category_title="🛡️ Quality & High Moat",
                category_tag="BUFFETT ECONOMIC MOAT",
                badge_color="indigo",
                catalyst=f"Tingkat pengembalian ekuitas prima (ROE {best_qual.profitability.roe:.1f}%) dan Piotroski F-Score {best_qual.quality.piotroski_f_score}/9 mencerminkan keunggulan kompetitif (moat) yang kokoh dalam menghasilkan laba jangka panjang."
            ))

        # -------------------------------------------------------------
        # Pick 4: Dividend Cash Cow
        # -------------------------------------------------------------
        # Criteria: Highest Dividend Yield with solvency safety (Altman >= 1.5, Piotroski >= 4, Score >= 50)
        candidates_div = [
            r for r in reports
            if r.ticker not in used_tickers
            and r.cash_flow_dividend.dividend_yield >= 3.5
            and r.composite_score >= 50.0
            and r.quality.piotroski_f_score >= 4
            and r.solvency.altman_z_score >= 1.5
        ]
        candidates_div.sort(key=lambda x: x.cash_flow_dividend.dividend_yield, reverse=True)

        if candidates_div:
            best_div = candidates_div[0]
            used_tickers.add(best_div.ticker)
            picks.append(self._build_top_pick_item(
                rep=best_div,
                category="DIVIDEND_CASH_COW",
                category_title="💰 Dividend Cash Cow",
                category_tag="HIGH CASH FLOW YIELD",
                badge_color="amber",
                catalyst=f"Imbal hasil dividen menarik ({best_div.cash_flow_dividend.dividend_yield:.1f}% Yield) didukung fundamental sehat (Score {best_div.composite_score:.1f}/100) dan konsisten membagikan keuntungan kepada investor."
            ))

        return picks


    def _build_top_pick_item(
        self,
        rep: EmitenAnalysisReport,
        category: str,
        category_title: str,
        category_tag: str,
        badge_color: str,
        catalyst: str
    ) -> TopPickItem:
        key_metrics = [
            f"ROE: {rep.profitability.roe:.1f}%",
            f"PER: {rep.valuation.per:.1f}x",
            f"PBV: {rep.valuation.pbv:.2f}x",
            f"Piotroski F: {rep.quality.piotroski_f_score}/9",
            f"Div Yield: {rep.cash_flow_dividend.dividend_yield:.1f}%"
        ]

        rationale = [
            f"Composite Score: {rep.composite_score:.1f}/100 (Grade {rep.grade}) - {rep.verdict.value}",
            f"Nilai Wajar Konsensus: Rp{rep.valuation.average_fair_value:,.0f} (Potensi Upside +{rep.valuation.upside_downside_pct:.1f}%)",
            f"Tingkat Solvabilitas: DER {rep.solvency.der:.2f}x | Altman Z {rep.solvency.altman_z_score:.2f} ({rep.solvency.altman_zone})"
        ]

        if rep.bank_metrics and rep.bank_metrics.get("is_bank"):
            rationale.append(f"Metrik Bank: NIM {rep.bank_metrics.get('nim', 0):.2f}% | NPL Gross {rep.bank_metrics.get('npl_gross', 0):.2f}% | CAR {rep.bank_metrics.get('car', 0):.2f}%")

        entry_zone = None
        tp1 = None
        tp2 = None
        sl = None
        rr = None
        buy_zone_lbl = None
        max_alloc = None

        if rep.buy_conviction:
            conv = rep.buy_conviction
            tp1 = conv.position_sizing.take_profit_1
            tp2 = conv.position_sizing.take_profit_2
            sl = conv.position_sizing.stop_loss_invalidation
            rr = conv.scenarios.risk_to_reward_ratio
            buy_zone_lbl = conv.scenarios.buy_zone_label
            max_alloc = conv.position_sizing.max_portfolio_allocation_pct
            min_entry = min(rep.current_price, round(rep.current_price * 0.985))
            entry_zone = f"Rp{min_entry:,.0f} - Rp{rep.current_price:,.0f}"
        else:
            tp1 = rep.valuation.average_fair_value
            sl = round(rep.current_price * 0.93)
            min_entry = round(rep.current_price * 0.985)
            entry_zone = f"Rp{min_entry:,.0f} - Rp{rep.current_price:,.0f}"

        return TopPickItem(
            ticker=rep.ticker,
            name=rep.name,
            sector=rep.sector,
            category=category,
            category_title=category_title,
            category_tag=category_tag,
            badge_color=badge_color,
            current_price=rep.current_price,
            fair_value=rep.valuation.average_fair_value,
            upside_pct=rep.valuation.upside_downside_pct,
            composite_score=rep.composite_score,
            grade=rep.grade,
            verdict=rep.verdict.value,
            per=rep.valuation.per,
            pbv=rep.valuation.pbv,
            roe=rep.profitability.roe,
            piotroski_f_score=rep.quality.piotroski_f_score,
            altman_z_score=rep.solvency.altman_z_score,
            dividend_yield=rep.cash_flow_dividend.dividend_yield,
            key_metrics_summary=key_metrics,
            rationale=rationale,
            catalyst=catalyst,
            entry_zone=entry_zone,
            take_profit_1=tp1,
            take_profit_2=tp2,
            stop_loss=sl,
            risk_to_reward_ratio=rr,
            buy_zone_label=buy_zone_lbl,
            max_allocation_pct=max_alloc
        )

