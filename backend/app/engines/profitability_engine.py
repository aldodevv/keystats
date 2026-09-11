"""
Profitability Engine: Computes DuPont 3-way ROE, ROIC, ROCE, and Margin Hierarchy (GPM, OPM, NPM).
"""

from app.models.keystats import RawKeyStats
from app.models.score import ProfitabilityResult


class ProfitabilityEngine:
    @staticmethod
    def calculate(raw: RawKeyStats) -> ProfitabilityResult:
        curr = raw.current_period
        rev = curr.revenue
        ni = curr.net_income
        assets = curr.total_assets
        equity = curr.total_equity
        ebit = curr.ebit if curr.ebit != 0 else curr.operating_profit
        
        # Margins
        gpm = (curr.gross_profit / rev * 100) if rev > 0 else 0.0
        opm = (curr.operating_profit / rev * 100) if rev > 0 else 0.0
        npm = (ni / rev * 100) if rev > 0 else 0.0
        
        # ROE & ROA
        roe = (ni / equity * 100) if equity > 0 else 0.0
        roa = (ni / assets * 100) if assets > 0 else 0.0
        
        # DuPont 3-Way Breakdown:
        # ROE = (Net Income / Revenue) * (Revenue / Assets) * (Assets / Equity)
        # ROE = Net Profit Margin * Asset Turnover * Financial Leverage Multiplier
        dupont_net_margin = (ni / rev) if rev > 0 else 0.0
        dupont_asset_turnover = (rev / assets) if assets > 0 else 0.0
        dupont_equity_multiplier = (assets / equity) if equity > 0 else 1.0
        
        # ROIC (Return on Invested Capital): NOPAT / Invested Capital
        # NOPAT approx = EBIT * (1 - 0.22 tax rate in Indonesia)
        # Invested Capital = Total Equity + Total Debt - Cash
        effective_tax_rate = 0.22
        nopat = ebit * (1 - effective_tax_rate)
        total_debt = curr.total_debt if curr.total_debt > 0 else (curr.short_term_debt + curr.long_term_debt)
        invested_capital = equity + total_debt - curr.cash_and_equivalents
        roic = (nopat / invested_capital * 100) if invested_capital > 0 else roe
        
        # ROCE (Return on Capital Employed): EBIT / Capital Employed
        # Capital Employed = Total Assets - Current Liabilities
        capital_employed = assets - curr.current_liabilities
        roce = (ebit / capital_employed * 100) if capital_employed > 0 else roa
        
        return ProfitabilityResult(
            roe=round(roe, 2),
            roa=round(roa, 2),
            roic=round(roic, 2),
            roce=round(roce, 2),
            gpm=round(gpm, 2),
            opm=round(opm, 2),
            npm=round(npm, 2),
            dupont_net_margin=round(dupont_net_margin, 4),
            dupont_asset_turnover=round(dupont_asset_turnover, 4),
            dupont_equity_multiplier=round(dupont_equity_multiplier, 2)
        )
