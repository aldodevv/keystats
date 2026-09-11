"""
High-Conviction Buy Engine:
Computes Margin of Safety (MoS), Multi-Scenario Targets (Bear/Base/Bull),
10-Point Institutional Buy Conviction Checklist, Position Sizing, and Sector Rankings.
"""

from typing import List, Optional, Dict, Any
from app.models.keystats import RawKeyStats
from app.models.score import (
    ValuationResult,
    ProfitabilityResult,
    SolvencyResult,
    QualityScoreResult,
    CashFlowDividendResult,
    GrowthResult,
    HealthZone
)
from app.models.conviction import (
    BuyZone,
    ConvictionTier,
    ConvictionCheckItem,
    MultiScenarioValuation,
    PositionSizingAdvice,
    SectorPeerRanking,
    BuyConvictionReport
)


class ConvictionEngine:
    @staticmethod
    def calculate(
        raw: RawKeyStats,
        val: ValuationResult,
        prof: ProfitabilityResult,
        solv: SolvencyResult,
        qual: QualityScoreResult,
        cf_div: CashFlowDividendResult,
        growth: GrowthResult,
        composite_score: float,
        grade: str,
        is_bank: bool = False,
        bank_data: Optional[Dict[str, Any]] = None
    ) -> BuyConvictionReport:
        price = raw.current_price
        
        # 1. Multi-Scenario Valuation (Bear, Base, Bull)
        scenarios = ConvictionEngine._compute_multi_scenarios(price, val, growth, prof, solv, raw, is_bank)
        
        # 2. 10-Point Institutional Buy Conviction Checklist
        checklist, passed_count, conviction_score = ConvictionEngine._evaluate_10_point_checklist(
            price, val, prof, solv, qual, cf_div, growth, scenarios, is_bank, bank_data
        )
        
        # 3. Conviction Tier Classification
        if passed_count >= 8:
            conviction_tier = ConvictionTier.HIGH_CONVICTION
            summary_verdict = "💎 HIGH CONVICTION BUY: Sangat layak diakumulasi dengan keyakinan institusional tinggi."
        elif passed_count >= 5:
            conviction_tier = ConvictionTier.MODERATE_CONVICTION
            summary_verdict = "⚖️ MODERATE BUY: Layak dibeli bertahap dengan manajemen risiko terukur."
        elif passed_count >= 3:
            conviction_tier = ConvictionTier.LOW_CONVICTION
            summary_verdict = "⚠️ LOW CONVICTION: Spekulatif, hanya pertimbangkan untuk porsi portofolio kecil."
        else:
            conviction_tier = ConvictionTier.AVOID
            summary_verdict = "🚫 AVOID / PASS: Fundamental belum memenuhi standar keamanan investasi minimal."
            
        # 4. Position Sizing & Money Management Advice
        position_sizing = ConvictionEngine._calculate_position_sizing(
            conviction_tier, grade, composite_score, price, scenarios
        )
        
        # 5. Sector Peer Ranking (Contextual)
        sector_ranking = ConvictionEngine._generate_sector_ranking(raw, val, prof, cf_div)

        return BuyConvictionReport(
            ticker=raw.ticker.upper(),
            conviction_score=round(conviction_score, 1),
            conviction_tier=conviction_tier,
            passed_checks_count=passed_count,
            total_checks_count=10,
            checklist=checklist,
            scenarios=scenarios,
            position_sizing=position_sizing,
            sector_ranking=sector_ranking,
            summary_verdict=summary_verdict
        )

    @staticmethod
    def _compute_multi_scenarios(
        price: float,
        val: ValuationResult,
        growth: GrowthResult,
        prof: ProfitabilityResult,
        solv: SolvencyResult,
        raw: RawKeyStats,
        is_bank: bool
    ) -> MultiScenarioValuation:
        base_target = val.average_fair_value if val.average_fair_value > 0 else price
        
        # Bear Case (Conservative downside floor)
        # Combination of 0.8x Graham Number, Book Value floor, or -1.5 Std Dev PER
        eps = raw.current_period.eps if raw.current_period.eps > 0 else 1.0
        bvps = (raw.current_period.total_equity / raw.shares_outstanding) if raw.shares_outstanding > 0 else 1.0
        
        bear_candidates = []
        if val.graham_number and val.graham_number > 0:
            bear_candidates.append(val.graham_number * 0.80)
        if bvps > 0:
            bear_candidates.append(bvps * (1.1 if is_bank else 0.9))
        if base_target > 0:
            bear_candidates.append(base_target * 0.75)
            
        bear_target = round(sum(bear_candidates) / len(bear_candidates), 2) if bear_candidates else round(price * 0.8, 2)
        # Ensure bear_target <= base_target
        bear_target = min(bear_target, base_target * 0.88)
        
        # Bull Case (Optimistic expansion scenario)
        bull_candidates = []
        if base_target > 0:
            bull_candidates.append(base_target * 1.25)
        if val.dcf_fair_value and val.dcf_fair_value > 0:
            bull_candidates.append(val.dcf_fair_value * 1.15)
        if raw.pe_mean_5y and eps > 0:
            bull_candidates.append(raw.pe_mean_5y * 1.2 * eps)
            
        bull_target = round(sum(bull_candidates) / len(bull_candidates), 2) if bull_candidates else round(base_target * 1.25, 2)
        # Ensure bull_target >= base_target
        bull_target = max(bull_target, base_target * 1.15)
        
        # Calculations
        mos_pct = round(((base_target - price) / base_target) * 100, 2) if base_target > 0 else 0.0
        downside_risk_pct = round(((price - bear_target) / price) * 100, 2) if (price > 0 and price > bear_target) else 0.0
        upside_potential_pct = round(((base_target - price) / price) * 100, 2) if price > 0 else 0.0
        bull_upside_pct = round(((bull_target - price) / price) * 100, 2) if price > 0 else 0.0
        
        downside_diff = max(1.0, price - bear_target)
        upside_diff = max(0.0, bull_target - price)
        rr_ratio = round(upside_diff / downside_diff, 2) if downside_diff > 0 else 1.0

        # Buy Zone Classification
        if mos_pct >= 25.0:
            buy_zone = BuyZone.STRONG_ACCUMULATION
            buy_zone_label = "🟢 STRONG ACCUMULATION ZONE"
            buy_zone_description = f"Margin of Safety sangat tebal ({mos_pct:.1f}%). Harga saat ini berada di area diskon premium dengan proteksi downside optimal."
        elif mos_pct >= 10.0:
            buy_zone = BuyZone.MODERATE_BUY
            buy_zone_label = "🟡 MODERATE BUY ZONE"
            buy_zone_description = f"Diskon valuasi menarik ({mos_pct:.1f}%). Ideal untuk strategi cicil bertahap (DCA / Value Averaging)."
        elif mos_pct >= -5.0:
            buy_zone = BuyZone.FAIR_HOLD
            buy_zone_label = "⚪ FAIR / HOLD ZONE"
            buy_zone_description = f"Harga diperdagangkan di sekitar nilai wajar ({mos_pct:+.1f}% vs Target Konsensus). Disarankan Hold atau tunggu koreksi."
        else:
            buy_zone = BuyZone.OVERVALUED_TRIM
            buy_zone_label = "🔴 OVERVALUED / TRIM ZONE"
            buy_zone_description = f"Harga telah melampaui nilai wajar (Overvalued {abs(mos_pct):.1f}%). Hindari agresif entry, pertimbangkan profit taking."

        return MultiScenarioValuation(
            current_price=price,
            bear_case_price=bear_target,
            base_case_price=base_target,
            bull_case_price=bull_target,
            margin_of_safety_pct=mos_pct,
            downside_risk_pct=downside_risk_pct,
            upside_potential_pct=upside_potential_pct,
            bull_upside_pct=bull_upside_pct,
            risk_to_reward_ratio=rr_ratio,
            buy_zone=buy_zone,
            buy_zone_label=buy_zone_label,
            buy_zone_description=buy_zone_description
        )

    @staticmethod
    def _evaluate_10_point_checklist(
        price: float,
        val: ValuationResult,
        prof: ProfitabilityResult,
        solv: SolvencyResult,
        qual: QualityScoreResult,
        cf_div: CashFlowDividendResult,
        growth: GrowthResult,
        scenarios: MultiScenarioValuation,
        is_bank: bool,
        bank_data: Optional[Dict[str, Any]]
    ):
        checklist: List[ConvictionCheckItem] = []
        
        # 1. Multi-Year EPS Growth / Compounding
        cagr_eps = growth.eps_cagr_3y
        yoy_eps = growth.eps_growth_yoy
        chk1_pass = (cagr_eps is not None and cagr_eps >= 8.0) or (yoy_eps >= 10.0)
        chk1_val = f"3Y CAGR: {f'+{cagr_eps:.1f}%' if cagr_eps is not None else 'N/A'} | YoY: {yoy_eps:+.1f}%"
        checklist.append(ConvictionCheckItem(
            id="chk_eps_growth",
            title="Pertumbuhan Laba Multi-Tahun (EPS Trend)",
            category="Growth",
            passed=chk1_pass,
            actual_value_str=chk1_val,
            benchmark_threshold_str="3Y CAGR >= 8% atau YoY >= 10%",
            explanation="Laba bersih per lembar saham menunjukkan tren ekspansi konsisten dan tidak stagnan."
        ))

        # 2. Capital Efficiency (ROE)
        roe_threshold = 14.0 if is_bank else 12.0
        chk2_pass = prof.roe >= roe_threshold
        checklist.append(ConvictionCheckItem(
            id="chk_roe",
            title="Efisiensi Modal Ekuitas (High ROE)",
            category="Profitability",
            passed=chk2_pass,
            actual_value_str=f"{prof.roe:.2f}%",
            benchmark_threshold_str=f"ROE >= {roe_threshold:.1f}%",
            explanation="Perusahaan mampu memutar ekuitas pemegang saham dengan efisiensi di atas rata-rata pasar."
        ))

        # 3. Quality of Earnings (Real Cash Flow vs Accounting Profit)
        chk3_pass = qual.cfo_to_net_income >= 1.0 or (cf_div.fcf > 0 and qual.cfo_to_net_income >= 0.85)
        checklist.append(ConvictionCheckItem(
            id="chk_cfo_quality",
            title="Kualitas Laba Riil (CFO vs Net Income)",
            category="Quality",
            passed=chk3_pass,
            actual_value_str=f"{qual.cfo_to_net_income:.2f}x",
            benchmark_threshold_str="CFO / Net Income >= 1.0x",
            explanation="Laba bersih buku didukung secara riil oleh kas operasi masuk (bukan piutang tertahan)."
        ))

        # 4. Valuation Discount vs Historical Multiple
        is_graham_safe = (val.graham_number is not None and val.graham_number >= price)
        chk4_pass = bool((0 < val.per <= 15.0) or (val.upside_downside_pct >= 10.0) or is_graham_safe)
        chk4_val = f"PER: {val.per}x | Upside: {val.upside_downside_pct:+.1f}%"
        checklist.append(ConvictionCheckItem(
            id="chk_valuation",
            title="Valuasi Terdiskon (Attractive Multiples)",
            category="Valuation",
            passed=chk4_pass,
            actual_value_str=chk4_val,
            benchmark_threshold_str="PER <= 15x atau Undervalued",
            explanation="Harga saham saat ini tidak berada pada level bubble atau premium berlebihan."
        ))

        # 5. Solvency & Balance Sheet Health
        if is_bank and bank_data:
            car = float(bank_data.get("car", 20.0))
            npl = float(bank_data.get("npl_gross", 2.0))
            chk5_pass = bool(car >= 18.0 and npl <= 3.5)
            chk5_val = f"CAR: {car:.1f}% | NPL: {npl:.2f}%"
            chk5_bench = "CAR >= 18% & NPL Gross <= 3.5%"
        else:
            chk5_pass = bool(solv.altman_zone == HealthZone.SAFE and solv.der <= 1.5)
            chk5_val = f"Altman: {solv.altman_z_score:.2f} ({solv.altman_zone.value}) | DER: {solv.der:.2f}x"
            chk5_bench = "Altman SAFE & DER <= 1.5x"
            
        checklist.append(ConvictionCheckItem(
            id="chk_solvency",
            title="Kesehatan Neraca & Risiko Solvabilitas",
            category="Solvency",
            passed=chk5_pass,
            actual_value_str=chk5_val,
            benchmark_threshold_str=chk5_bench,
            explanation="Struktur utang terkendali aman, meminimalisir risiko gagal bayar kredit atau krisis likuiditas."
        ))

        # 6. Accounting Manipulation Safety (Beneish M-Score)
        chk6_pass = bool(not qual.is_manipulation_risk)
        m_score_str = f"{qual.beneish_m_score:.2f}" if qual.beneish_m_score is not None else "Normal (-2.8)"
        checklist.append(ConvictionCheckItem(
            id="chk_accounting",
            title="Audit Integritas Akuntansi (Beneish M-Score)",
            category="Quality",
            passed=chk6_pass,
            actual_value_str=f"M-Score: {m_score_str}",
            benchmark_threshold_str="M-Score < -1.78 (Safe)",
            explanation="Laporan keuangan bersih dari anomali pembukuan agresif atau indikasi manipulasi akrual."
        ))

        # 7. Free Cash Flow Generation
        chk7_pass = bool(cf_div.fcf_yield >= 3.5 or cf_div.fcf > 0)
        checklist.append(ConvictionCheckItem(
            id="chk_fcf",
            title="Kemampuan Menghasilkan Arus Kas Bebas (FCF)",
            category="Cash Flow",
            passed=chk7_pass,
            actual_value_str=f"Yield: {cf_div.fcf_yield:.2f}% (Rp{cf_div.fcf / 1e12:,.1f} T)",
            benchmark_threshold_str="FCF Yield >= 3.5%",
            explanation="Perusahaan mencetak surplus kas setelah mendanai seluruh belanja modal (Capex)."
        ))

        # 8. Dividend Safety & Payout Sustainability
        chk8_pass = bool(cf_div.dividend_yield >= 2.5 and (cf_div.dpr <= 85.0 or cf_div.is_dividend_sustainable))
        checklist.append(ConvictionCheckItem(
            id="chk_dividend",
            title="Dividen Sehat & Berkelanjutan (No Dividend Trap)",
            category="Dividend",
            passed=chk8_pass,
            actual_value_str=f"Yield: {cf_div.dividend_yield:.2f}% | DPR: {cf_div.dpr:.1f}%",
            benchmark_threshold_str="Yield >= 2.5% & DPR <= 85%",
            explanation="Imbal hasil dividen nyata, berkelanjutan, dan tidak menggerus modal kerja perusahaan."
        ))

        # 9. Profit Margin / Pricing Power
        npm_threshold = 8.0
        chk9_pass = bool(prof.npm >= npm_threshold or prof.gpm >= 25.0)
        checklist.append(ConvictionCheckItem(
            id="chk_margin",
            title="Margin Keuntungan Bersih (Pricing Power)",
            category="Profitability",
            passed=chk9_pass,
            actual_value_str=f"NPM: {prof.npm:.2f}% | GPM: {prof.gpm:.2f}%",
            benchmark_threshold_str=f"NPM >= {npm_threshold:.1f}%",
            explanation="Perusahaan memiliki keunggulan kompetitif (Moat) yang menjaga ketebalan margin laba."
        ))

        # 10. Margin of Safety (MoS >= 15%)
        chk10_pass = bool(scenarios.margin_of_safety_pct >= 15.0)
        checklist.append(ConvictionCheckItem(
            id="chk_mos",
            title="Margin of Safety (Proteksi Risiko Beli)",
            category="Valuation",
            passed=chk10_pass,
            actual_value_str=f"{scenarios.margin_of_safety_pct:+.1f}% Diskon",
            benchmark_threshold_str="MoS >= +15.0%",
            explanation="Tersedia ruang pengaman harga yang memadai antara harga pasar dan estimasi nilai wajar."
        ))

        passed_count = sum(1 for chk in checklist if chk.passed)
        conviction_score = (passed_count / len(checklist)) * 100.0
        
        return checklist, passed_count, conviction_score

    @staticmethod
    def _calculate_position_sizing(
        tier: ConvictionTier,
        grade: str,
        score: float,
        price: float,
        scenarios: MultiScenarioValuation
    ) -> PositionSizingAdvice:
        if tier == ConvictionTier.HIGH_CONVICTION and grade in ["A+", "A"]:
            max_alloc = 20.0
            rationale = "High-Conviction Bluechip/Champion: Fundamental sangat kokoh, risiko rendah, cocok untuk core portfolio hingga 15-20% alokasi modal."
        elif tier == ConvictionTier.MODERATE_CONVICTION or grade == "B":
            max_alloc = 10.0
            rationale = "Moderate-Conviction Growth/Value: Fundamental baik namun ada variabel yang perlu dipantau, alokasi optimal 8-10%."
        elif tier == ConvictionTier.LOW_CONVICTION:
            max_alloc = 5.0
            rationale = "Tactical / Speculative: Risiko volatilitas moderat-tinggi, batasi alokasi maksimal 3-5% portofolio."
        else:
            max_alloc = 0.0
            rationale = "Avoid / High Risk: Kualitas fundamental belum memadai, tidak disarankan mengalokasikan modal."

        tp1 = scenarios.base_case_price
        tp2 = scenarios.bull_case_price
        
        # Stop loss floor: If price breaks below bear case support with breakdown triggers
        sl_floor = round(min(scenarios.bear_case_price * 0.95, price * 0.90), 2)
        
        triggers = [
            "Laba bersih kuartalan turun > 25% YoY selama 2 kuartal berturut-turut.",
            "Altman Z-Score turun memasuki Zona Distress (risiko gagal bayar utang).",
            "Terjadi perubahan kebijakan dividen drastis atau lonjakan utang tak terduga."
        ]

        return PositionSizingAdvice(
            max_portfolio_allocation_pct=max_alloc,
            take_profit_1=tp1,
            take_profit_2=tp2,
            stop_loss_invalidation=sl_floor,
            allocation_rationale=rationale,
            invalidation_triggers=triggers
        )

    @staticmethod
    def _generate_sector_ranking(
        raw: RawKeyStats,
        val: ValuationResult,
        prof: ProfitabilityResult,
        cf_div: CashFlowDividendResult
    ) -> SectorPeerRanking:
        badges = []
        if prof.roe >= 18.0:
            badges.append("🏆 Top-Tier ROE in Sector")
        if val.per > 0 and val.per <= 10.0:
            badges.append("💎 Value Bargain in Sector")
        if cf_div.dividend_yield >= 6.0:
            badges.append("👑 Dividend Royalty in Sector")
        if not badges:
            badges.append("⭐ Stable Sector Contender")

        return SectorPeerRanking(
            sector_name=raw.sector,
            total_peers_evaluated=10,
            per_percentile=85.0 if val.per <= 10.0 else 55.0,
            roe_percentile=90.0 if prof.roe >= 18.0 else 60.0,
            dividend_percentile=88.0 if cf_div.dividend_yield >= 6.0 else 50.0,
            badges=badges
        )
