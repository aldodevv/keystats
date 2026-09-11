"""
Master Scoring & Synthesis Engine:
Computes the 5-axis Radar Scores, Composite Fundamental Score (0-100),
Letter Grade (A+ to F), Final Verdict, and Bull/Bear Case Synthesizer.
"""

from typing import List, Optional, Dict, Any
from app.models.keystats import RawKeyStats
from app.models.xbrl import XBRLEntryPoint
from app.models.score import (
    ValuationResult,
    ProfitabilityResult,
    SolvencyResult,
    QualityScoreResult,
    LiquidityResult,
    CashFlowDividendResult,
    GrowthResult,
    RadarScore,
    VerdictAction,
    EmitenAnalysisReport,
    HealthZone,
    PriceSensitivityScenario
)
from app.engines.valuation_engine import ValuationEngine
from app.engines.profitability_engine import ProfitabilityEngine
from app.engines.financial_health import FinancialHealthEngine
from app.engines.sector_bank_engine import SectorBankEngine
from app.engines.conviction_engine import ConvictionEngine


class ScoringEngine:
    @staticmethod
    def analyze_emiten(raw: RawKeyStats) -> EmitenAnalysisReport:
        # 1. Compute Base Engines
        prof = ProfitabilityEngine.calculate(raw)
        growth = FinancialHealthEngine.calculate_growth(raw)
        val = ValuationEngine.calculate(raw, eps_growth_rate=growth.eps_growth_yoy)
        solv = FinancialHealthEngine.calculate_solvency(raw)
        liq = FinancialHealthEngine.calculate_liquidity(raw)
        qual = FinancialHealthEngine.calculate_quality(raw)
        cf_div = FinancialHealthEngine.calculate_cash_flow_dividend(raw)
        
        # Sector specific adjustments
        is_bank = (
            getattr(raw, "xbrl_entry_point", None) == XBRLEntryPoint.FINANCIAL_BANKING or
            "bank" in raw.sector.lower() or
            "financial" in raw.sector.lower() or
            raw.bank_metrics is not None
        )
        bank_data = SectorBankEngine.evaluate_bank(raw) if is_bank else None
        
        # 2. Compute 5-Axis Radar Scores (0 to 100)
        radar = ScoringEngine._compute_radar(val, prof, solv, growth, qual, cf_div, is_bank, bank_data)
        
        # 3. Composite Weighted Score
        # Weighting: Profitability (25%), Valuation (25%), Solvency/Health (20%), Cash Flow (15%), Growth (15%)
        composite_score = round(
            (radar.profitability * 0.25) +
            (radar.valuation * 0.25) +
            (radar.financial_health * 0.20) +
            (radar.cash_flow_quality * 0.15) +
            (radar.growth * 0.15),
            1
        )
        
        # 4. Grade & Verdict
        grade = ScoringEngine._determine_grade(composite_score)
        verdict = ScoringEngine._determine_verdict(composite_score, val, solv, qual)

        # 5. Flags and Bull/Bear cases
        bulls, bears, greens, reds = ScoringEngine._generate_insights(raw, val, prof, solv, qual, cf_div, growth, bank_data)

        # 6. Price Sensitivity Simulation Scenarios (-15% to +15%)
        scenarios = ScoringEngine._generate_price_sensitivity(raw, val, prof, solv, qual, cf_div, growth, is_bank, bank_data)

        # 7. High-Conviction Buy Engine (MoS, Buy Zone, 10-Point Checklist, Position Sizing)
        buy_conviction = ConvictionEngine.calculate(
            raw, val, prof, solv, qual, cf_div, growth, composite_score, grade, is_bank, bank_data
        )

        return EmitenAnalysisReport(
            ticker=raw.ticker.upper(),
            name=raw.name,
            sector=raw.sector,
            industry=raw.industry,
            current_price=raw.current_price,
            previous_close=raw.previous_close,
            price_change_pct=raw.price_change_pct or 0.0,
            is_realtime_price=raw.is_realtime,
            market_cap=raw.market_cap,
            revenue=raw.current_period.revenue,
            net_income=raw.current_period.net_income,
            eps=raw.current_period.eps,
            valuation=val,
            profitability=prof,
            solvency=solv,
            quality=qual,
            liquidity=liq,
            cash_flow_dividend=cf_div,
            growth=growth,
            bank_metrics=bank_data,
            composite_score=composite_score,
            grade=grade,
            radar=radar,
            verdict=verdict,
            price_sensitivity_scenarios=scenarios,
            bull_cases=bulls,
            bear_cases=bears,
            green_flags=greens,
            red_flags=reds,
            buy_conviction=buy_conviction,
            financial_matrix=raw.financial_matrix
        )

    @staticmethod
    def _compute_radar(
        val: ValuationResult,
        prof: ProfitabilityResult,
        solv: SolvencyResult,
        growth: GrowthResult,
        qual: QualityScoreResult,
        cf: CashFlowDividendResult,
        is_bank: bool,
        bank_data: Optional[Dict[str, Any]] = None
    ) -> RadarScore:
        # A. Valuation Score (0-100)
        # Higher score = More undervalued / Attractive price
        val_score = 50.0
        if val.upside_downside_pct > 30: val_score += 30
        elif val.upside_downside_pct > 15: val_score += 20
        elif val.upside_downside_pct > 0: val_score += 10
        elif val.upside_downside_pct < -30: val_score -= 30
        elif val.upside_downside_pct < -15: val_score -= 20
        
        if 0 < val.per < 12: val_score += 15
        elif val.per > 25: val_score -= 15
        
        if 0 < val.pbv < 1.5: val_score += 10
        elif val.pbv > 4.0: val_score -= 10
        
        if val.peg_ratio and 0 < val.peg_ratio < 1.0: val_score += 10
        val_score = max(5.0, min(100.0, val_score))
        
        # B. Profitability Score (0-100)
        prof_score = 40.0
        if prof.roe >= 20.0: prof_score += 30
        elif prof.roe >= 14.0: prof_score += 20
        elif prof.roe >= 8.0: prof_score += 10
        elif prof.roe < 0: prof_score -= 25
        
        if prof.npm >= 18.0: prof_score += 15
        elif prof.npm >= 10.0: prof_score += 10
        elif prof.npm < 3.0: prof_score -= 10
        
        if prof.roic >= 15.0: prof_score += 15
        prof_score = max(5.0, min(100.0, prof_score))
        
        # C. Financial Health & Solvency (0-100)
        health_score = 50.0
        if is_bank and bank_data:
            health_score = bank_data.get("bank_health_score", 70.0)
        else:
            if solv.altman_zone == HealthZone.SAFE: health_score += 25
            elif solv.altman_zone == HealthZone.DISTRESS: health_score -= 30
            
            if solv.der <= 0.5: health_score += 15
            elif solv.der <= 1.0: health_score += 10
            elif solv.der > 2.0: health_score -= 20
            
            if solv.net_debt_to_equity < 0: health_score += 10  # Net Cash Company
            
        health_score = max(5.0, min(100.0, health_score))
        
        # D. Growth Score (0-100)
        growth_score = 45.0
        if growth.eps_growth_yoy >= 20.0: growth_score += 20
        elif growth.eps_growth_yoy >= 10.0: growth_score += 12
        elif growth.eps_growth_yoy < 0: growth_score -= 15
        
        if growth.revenue_growth_yoy >= 15.0: growth_score += 15
        elif growth.revenue_growth_yoy >= 8.0: growth_score += 8
        elif growth.revenue_growth_yoy < 0: growth_score -= 10
        
        # Multi-year CAGR compounding bonus
        if growth.eps_cagr_3y and growth.eps_cagr_3y >= 12.0: growth_score += 10
        elif growth.eps_cagr_3y and growth.eps_cagr_3y >= 6.0: growth_score += 5
        elif growth.eps_cagr_3y and growth.eps_cagr_3y < -5.0: growth_score -= 10
        
        if growth.revenue_cagr_3y and growth.revenue_cagr_3y >= 10.0: growth_score += 8
        elif growth.revenue_cagr_3y and growth.revenue_cagr_3y >= 5.0: growth_score += 4
        
        growth_score = max(5.0, min(100.0, growth_score))
        
        # E. Cash Flow & Quality Score (0-100)
        cf_score = 40.0
        # Piotroski F-Score weight (9 max)
        cf_score += (qual.piotroski_f_score / 9.0) * 35.0
        
        if qual.cfo_to_net_income >= 1.0: cf_score += 15
        elif qual.cfo_to_net_income < 0.5: cf_score -= 10
        
        if cf.fcf_yield >= 7.0: cf_score += 15
        elif cf.fcf_yield > 0: cf_score += 8
        elif cf.fcf < 0: cf_score -= 10
        
        cf_score = max(5.0, min(100.0, cf_score))
        
        return RadarScore(
            valuation=round(val_score, 1),
            profitability=round(prof_score, 1),
            financial_health=round(health_score, 1),
            growth=round(growth_score, 1),
            cash_flow_quality=round(cf_score, 1)
        )

    @staticmethod
    def _determine_grade(score: float) -> str:
        if score >= 85.0: return "A+"
        elif score >= 75.0: return "A"
        elif score >= 65.0: return "B"
        elif score >= 50.0: return "C"
        elif score >= 35.0: return "D"
        else: return "F"

    @staticmethod
    def _determine_verdict(
        score: float,
        val: ValuationResult,
        solv: SolvencyResult,
        qual: QualityScoreResult
    ) -> VerdictAction:
        if solv.altman_zone == HealthZone.DISTRESS or qual.is_manipulation_risk or score < 40.0:
            return VerdictAction.AVOID
        if score >= 75.0 and val.upside_downside_pct > 10.0 and qual.piotroski_f_score >= 6:
            return VerdictAction.STRONG_BUY
        if score >= 60.0 and val.upside_downside_pct >= 0:
            return VerdictAction.BUY
        if score >= 50.0:
            return VerdictAction.HOLD
        return VerdictAction.SPECULATIVE

    @staticmethod
    def _generate_insights(
        raw: RawKeyStats,
        val: ValuationResult,
        prof: ProfitabilityResult,
        solv: SolvencyResult,
        qual: QualityScoreResult,
        cf: CashFlowDividendResult,
        growth: GrowthResult,
        bank_data: Optional[Dict[str, Any]] = None
    ):
        bulls = []
        bears = []
        greens = []
        reds = []
        
        # Valuation insights
        if val.upside_downside_pct > 15:
            bulls.append(f"Potensi upside valuasi menarik ({val.upside_downside_pct}% menuju target Rp{val.average_fair_value:,.0f}).")
            greens.append(f"Valuasi tergolong murah (Undervalued vs DCF/Graham).")
        elif val.upside_downside_pct < -20:
            bears.append(f"Harga saat ini di atas nilai wajar historis (Overvalued {abs(val.upside_downside_pct)}%).")
            reds.append("Valuasi mahal / Price trading at premium.")
            
        if val.peg_ratio and val.peg_ratio < 1.0:
            greens.append(f"PEG Ratio sangat atraktif ({val.peg_ratio}x), pertumbuhan laba melampaui valuasi.")
            
        # Profitability insights
        if prof.roe >= 15.0:
            bulls.append(f"Efisiensi ekuitas prima dengan ROE solid {prof.roe}% (High Capital Productivity).")
            greens.append(f"ROE unggul di level {prof.roe}%.")
        elif prof.roe < 6.0:
            bears.append(f"Profitabilitas tertekan (ROE rendah di {prof.roe}%).")
            reds.append("Kemampuan menghasilkan laba ekuitas di bawah standar IDX.")
            
        if prof.npm >= 15.0:
            greens.append(f"Margin laba bersih (NPM) tebal di {prof.npm}%.")
            
        # Quality & Solvency
        if qual.piotroski_f_score >= 7:
            bulls.append(f"Piotroski F-Score istimewa ({qual.piotroski_f_score}/9) menandakan perbaikan fundamental berkelanjutan.")
            greens.append("Kualitas fundamental top-tier (Piotroski >= 7).")
        elif qual.piotroski_f_score <= 3:
            reds.append(f"Piotroski F-Score rendah ({qual.piotroski_f_score}/9), waspadai penurunan efisiensi.")
            
        if qual.cfo_to_net_income >= 1.0:
            greens.append("Quality of Earnings tinggi: laba bersih didukung penuh oleh arus kas operasi riil (CFO > NI).")
        else:
            reds.append("Quality of Earnings rendah: arus kas operasi lebih kecil dari laba buku akrual.")
            
        if solv.altman_zone == HealthZone.SAFE:
            greens.append(f"Altman Z-Score berada di Zona Aman ({solv.altman_z_score}), risiko kebangkrutan sangat rendah.")
        elif solv.altman_zone == HealthZone.DISTRESS:
            reds.append(f"PERINGATAN: Altman Z-Score ({solv.altman_z_score}) masuk Zona Distress.")
            bears.append("Struktur permodalan berisiko tinggi terhadap gagal bayar kewajiban.")
            
        if solv.der > 2.0:
            reds.append(f"Rasio utang tinggi (DER: {solv.der}x).")
        elif solv.net_debt_to_equity < 0:
            greens.append("Perusahaan posisi Net Cash (Kas lebih besar dari seluruh utang berbunga).")
            
        # Dividend & Cash flow
        if cf.dividend_yield >= 5.0:
            bulls.append(f"Imbal hasil dividen menarik ({cf.dividend_yield}% Yield) dengan cash payout terjaga.")
            greens.append(f"Dividend Cash Cow ({cf.dividend_yield}% Yield).")
            
        # Growth & EPS Insights
        if growth.eps_growth_yoy > 15.0:
            bulls.append(f"Pertumbuhan EPS YoY kuat di angka +{growth.eps_growth_yoy}%.")
            greens.append(f"Laba per lembar saham naik +{growth.eps_growth_yoy}% YoY.")
        elif growth.eps_growth_yoy < -10.0:
            bears.append(f"Terjadi kontraksi pertumbuhan laba EPS YoY ({growth.eps_growth_yoy}%).")
            reds.append(f"EPS terkontraksi {growth.eps_growth_yoy}% YoY.")
            
        if growth.eps_cagr_3y and growth.eps_cagr_3y >= 10.0:
            bulls.append(f"Pertumbuhan EPS multi-tahun solid (3-Year CAGR +{growth.eps_cagr_3y}%).")
            greens.append(f"Konsistensi pertumbuhan EPS jangka panjang (CAGR {growth.eps_cagr_3y}%).")
        elif growth.eps_cagr_3y and growth.eps_cagr_3y < -5.0:
            bears.append(f"Tren EPS multi-tahun menurun (3-Year CAGR {growth.eps_cagr_3y}%).")
            
        if growth.revenue_cagr_3y and growth.revenue_cagr_3y >= 10.0:
            greens.append(f"Ekspansi pendapatan konsisten (Revenue 3Y CAGR +{growth.revenue_cagr_3y}%).")
            
        # Bank specific insights
        if bank_data:
            for s in bank_data.get("bank_strengths", []):
                greens.append(s)
            for f in bank_data.get("bank_flags", []):
                reds.append(f)
                
        return bulls, bears, greens, reds

    @staticmethod
    def _generate_price_sensitivity(
        raw: RawKeyStats,
        val: ValuationResult,
        prof: ProfitabilityResult,
        solv: SolvencyResult,
        qual: QualityScoreResult,
        cf: CashFlowDividendResult,
        growth: GrowthResult,
        is_bank: bool,
        bank_data: Optional[Dict[str, Any]] = None
    ) -> List[PriceSensitivityScenario]:
        """Calculates how composite fundamental score and verdict change dynamically across price scenarios."""
        scenarios = []
        base_price = raw.current_price
        eps = raw.current_period.eps if raw.current_period.eps > 0 else (raw.current_period.net_income / raw.shares_outstanding if raw.shares_outstanding > 0 else 1.0)
        bvps = (raw.current_period.total_equity / raw.shares_outstanding) if (raw.shares_outstanding > 0 and raw.current_period.total_equity > 0) else 1.0
        dps = raw.dps if raw.dps > 0 else (raw.current_period.dividends_paid / raw.shares_outstanding if raw.shares_outstanding > 0 else 0.0)
        fair_val = val.average_fair_value
        
        # Test 7 price deltas: -15%, -10%, -5%, 0%, +5%, +10%, +15%
        deltas = [-15.0, -10.0, -5.0, 0.0, 5.0, 10.0, 15.0]
        
        for delta in deltas:
            sim_price = round(base_price * (1 + (delta / 100.0)), 0)
            sim_per = round(sim_price / eps, 2) if eps > 0 else 0.0
            sim_pbv = round(sim_price / bvps, 2) if bvps > 0 else 0.0
            sim_div_yield = round((dps / sim_price * 100), 2) if sim_price > 0 else 0.0
            sim_upside = round(((fair_val - sim_price) / sim_price * 100), 1) if sim_price > 0 else 0.0
            
            # Simulated valuation result
            sim_val = ValuationResult(
                per=sim_per,
                pbv=sim_pbv,
                ev_ebitda=val.ev_ebitda,
                peg_ratio=round(sim_per / growth.eps_growth_yoy, 2) if (growth.eps_growth_yoy > 1.0 and sim_per > 0) else None,
                graham_number=val.graham_number,
                dcf_fair_value=val.dcf_fair_value,
                average_fair_value=fair_val,
                upside_downside_pct=sim_upside,
                is_undervalued=sim_upside > 10.0
            )
            
            # Recalculate Radar & Composite Score for simulated price
            sim_radar = ScoringEngine._compute_radar(sim_val, prof, solv, growth, qual, cf, is_bank, bank_data)
            sim_composite = round(
                (sim_radar.profitability * 0.25) +
                (sim_radar.valuation * 0.25) +
                (sim_radar.financial_health * 0.20) +
                (sim_radar.cash_flow_quality * 0.15) +
                (sim_radar.growth * 0.15),
                1
            )
            sim_verdict = ScoringEngine._determine_verdict(sim_composite, sim_val, solv, qual)
            
            scenarios.append(PriceSensitivityScenario(
                price_change_pct=delta,
                simulated_price=sim_price,
                per=sim_per,
                pbv=sim_pbv,
                dividend_yield=sim_div_yield,
                upside_pct=sim_upside,
                composite_score=sim_composite,
                verdict=sim_verdict.value
            ))
            
        return scenarios
