"""
Unit tests for Valuation Engine calculations (DCF, Graham, PEG, Bands).
"""

import pytest
import math
from app.engines.valuation_engine import ValuationEngine
from app.models.keystats import RawKeyStats, FinancialPeriod


def test_graham_number_calculation():
    # Setup dummy stock with known EPS and BVPS
    # Graham Number = sqrt(22.5 * 400 * 2000) = sqrt(18,000,000) = 4242.64
    raw = RawKeyStats(
        ticker="TEST",
        name="Test Company Tbk",
        current_price=4000.0,
        shares_outstanding=1_000_000_000,
        market_cap=4_000_000_000_000,
        current_period=FinancialPeriod(
            year=2024,
            revenue=10_000_000_000_000,
            gross_profit=4_000_000_000_000,
            operating_profit=1_000_000_000_000,
            net_income=400_000_000_000,
            eps=400.0,
            total_equity=2_000_000_000_000,
            shares_outstanding=1_000_000_000
        )
    )
    res = ValuationEngine.calculate(raw, eps_growth_rate=15.0)
    
    assert res.per == 10.0  # 4000 / 400
    assert res.pbv == 2.0   # 4000 / 2000
    assert res.peg_ratio == 0.67  # 10 / 15
    assert res.graham_number is not None
    assert math.isclose(res.graham_number, 4242.64, rel_tol=1e-2)


def test_dcf_valuation_positive_fcf():
    raw = RawKeyStats(
        ticker="TEST_DCF",
        name="Test Cash Generator Tbk",
        current_price=1000.0,
        shares_outstanding=1_000_000,
        market_cap=1_000_000_000,
        current_period=FinancialPeriod(
            year=2024,
            revenue=500_000_000,
            net_income=100_000_000,
            fcf=80_000_000,
            cash_and_equivalents=20_000_000,
            total_debt=10_000_000,
            shares_outstanding=1_000_000
        )
    )
    res = ValuationEngine.calculate(raw)
    assert res.dcf_fair_value is not None
    assert res.dcf_fair_value > 0
