"""
Valuation Engine:
Computes traditional & advanced valuation metrics including PER, PBV, EV/EBITDA, PEG,
Graham Number, Multi-stage DCF, Justified PBV (for Banks), and Historical Valuation Bands.
Incorporates point-in-time data isolation to prevent look-ahead bias.
"""

import math
from typing import Optional
from app.models.keystats import RawKeyStats
from app.models.score import ValuationResult
from app.models.xbrl import XBRLEntryPoint


class ValuationEngine:
    @staticmethod
    def calculate(raw: RawKeyStats, eps_growth_rate: Optional[float] = None) -> ValuationResult:
        price = raw.current_price
        curr = raw.current_period
        shares = raw.shares_outstanding if raw.shares_outstanding > 0 else 1.0
        market_cap = raw.market_cap if raw.market_cap > 0 else (price * shares)
        is_bank = (
            raw.xbrl_entry_point == XBRLEntryPoint.FINANCIAL_BANKING or
            "bank" in raw.sector.lower() or
            "bank" in raw.industry.lower() or
            raw.bank_metrics is not None
        )
        
        # EPS & BVPS (Point-in-Time as-reported)
        eps = curr.eps if curr.eps != 0 else (curr.net_income / shares if shares > 0 else 0.0)
        bvps = (curr.total_equity / shares) if (shares > 0 and curr.total_equity > 0) else 0.0
        
        # 1. PER
        per = (price / eps) if eps > 0 else 0.0
        
        # 2. PBV
        pbv = (price / bvps) if bvps > 0 else 0.0
        
        # 2b. Price to Sales (P/S)
        ps_ratio = (market_cap / curr.revenue) if curr.revenue > 0 else 0.0
        
        # 3. Enterprise Value & EV/EBITDA (Applicable to non-banks; for banks, set based on market cap)
        if is_bank:
            ev = market_cap
            ev_ebitda = per  # For banks, PER is the prime operational multiple
        else:
            total_debt = curr.total_debt if curr.total_debt > 0 else (curr.short_term_debt + curr.long_term_debt)
            cash = curr.cash_and_equivalents
            ev = market_cap + total_debt - cash
            ebitda = curr.ebitda if curr.ebitda > 0 else (curr.operating_profit + (curr.total_assets * 0.05))
            ev_ebitda = (ev / ebitda) if ebitda > 0 else 0.0
        
        # 4. PEG Ratio
        peg_ratio = None
        if eps_growth_rate is not None and eps_growth_rate > 1.0 and per > 0:
            peg_ratio = round(per / eps_growth_rate, 2)
            
        # 5. Graham Number: sqrt(22.5 * EPS * BVPS)
        graham_number = None
        if eps > 0 and bvps > 0:
            product = 22.5 * eps * bvps
            if product > 0:
                graham_number = round(math.sqrt(product), 2)
                
        # 6. Discounted Cash Flow (DCF) or Justified PBV (for Banking)
        dcf_fair_value = ValuationEngine._calculate_dcf(raw, shares, is_bank, bvps)
        
        # 7. Historical Valuation Bands Analysis
        pe_status = ValuationEngine._analyze_band(per, raw.pe_mean_5y, raw.pe_standard_deviation, "PER")
        pbv_status = ValuationEngine._analyze_band(pbv, raw.pbv_mean_5y, raw.pbv_standard_deviation, "PBV")
        
        # 8. Composite Fair Value Estimation (Without Look-Ahead Bias)
        fair_values = []
        if graham_number and graham_number > 0:
            fair_values.append(graham_number)
        if dcf_fair_value and dcf_fair_value > 0:
            fair_values.append(dcf_fair_value)
        if raw.pe_mean_5y and raw.pe_mean_5y > 0 and eps > 0:
            historical_pe_value = raw.pe_mean_5y * eps
            fair_values.append(historical_pe_value)
        if raw.pbv_mean_5y and raw.pbv_mean_5y > 0 and bvps > 0:
            historical_pbv_value = raw.pbv_mean_5y * bvps
            fair_values.append(historical_pbv_value)
            
        if fair_values:
            average_fair_value = round(sum(fair_values) / len(fair_values), 2)
        else:
            average_fair_value = round(bvps * 1.5 if bvps > 0 else price, 2)
            
        upside_downside_pct = round(((average_fair_value - price) / price) * 100, 2) if price > 0 else 0.0
        is_undervalued = upside_downside_pct > 10.0
        
        return ValuationResult(
            per=round(per, 2),
            pbv=round(pbv, 2),
            ps_ratio=round(ps_ratio, 2),
            ev_ebitda=round(ev_ebitda, 2),
            peg_ratio=peg_ratio,
            graham_number=graham_number,
            dcf_fair_value=dcf_fair_value,
            historical_pe_band_status=pe_status,
            historical_pbv_band_status=pbv_status,
            average_fair_value=average_fair_value,
            upside_downside_pct=upside_downside_pct,
            is_undervalued=is_undervalued
        )

    @staticmethod
    def _calculate_dcf(raw: RawKeyStats, shares: float, is_bank: bool = False, bvps: float = 0.0) -> Optional[float]:
        """
        Calculates 5-year conservative DCF / Gordon Growth model.
        For banks, uses Justified P/B Gordon formula: Fair BVPS Multiple = (ROE - g) / (Ke - g).
        """
        curr = raw.current_period
        
        # Branching for Banks: Justified Price-to-Book Model
        if is_bank and bvps > 0:
            equity = curr.total_equity if curr.total_equity > 0 else 1.0
            roe = curr.net_income / equity if equity > 0 else 0.15
            ke = 0.11  # 11% Cost of Equity for Indonesian Tier-1/Tier-2 Banks
            g = 0.06   # 6% Sustainable long-term credit & economic growth
            
            if ke > g:
                justified_pbv = (roe - g) / (ke - g)
                justified_pbv = max(0.8, min(justified_pbv, 5.0))
                return round(bvps * justified_pbv, 2)
                
        # Corporate Multi-Stage DCF
        base_fcf = curr.fcf
        if base_fcf <= 0:
            if curr.cfo > 0:
                base_fcf = curr.cfo - abs(curr.capex)
            if base_fcf <= 0 and curr.net_income > 0:
                base_fcf = curr.net_income * 0.7
                
        if base_fcf <= 0 or shares <= 0:
            return None
            
        wacc = 0.10  # 10% discount rate
        terminal_growth = 0.03
        fcf_growth = 0.07
        
        pv_future_fcf = 0.0
        projected_fcf = base_fcf
        for year in range(1, 6):
            projected_fcf *= (1 + fcf_growth)
            pv_future_fcf += projected_fcf / ((1 + wacc) ** year)
            
        terminal_value = (projected_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
        pv_terminal_value = terminal_value / ((1 + wacc) ** 5)
        
        enterprise_value = pv_future_fcf + pv_terminal_value
        total_debt = curr.total_debt if curr.total_debt > 0 else (curr.short_term_debt + curr.long_term_debt)
        equity_value = enterprise_value + curr.cash_and_equivalents - total_debt
        
        if equity_value <= 0:
            return None
            
        return round(equity_value / shares, 2)

    @staticmethod
    def _analyze_band(current_val: float, mean: Optional[float], std: Optional[float], metric_name: str) -> Optional[str]:
        if not mean or not std or current_val <= 0:
            return None
            
        diff = current_val - mean
        z = diff / std if std > 0 else 0
        
        if z <= -1.5:
            return f"Below -1.5σ Band (Extremely Cheap {metric_name})"
        elif z <= -0.5:
            return f"Below Mean (-1.0σ Band - Undervalued {metric_name})"
        elif z <= 0.5:
            return f"Near Historical Mean (Fair {metric_name})"
        elif z <= 1.5:
            return f"Above Mean (+1.0σ Band - Premium {metric_name})"
        else:
            return f"Above +1.5σ Band (Expensive {metric_name})"
