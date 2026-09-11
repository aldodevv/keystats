"""
Unit and Integration Tests for High-Conviction Buy Engine,
Margin of Safety, Multi-Scenario Valuation, 10-Point Checklist, and Position Sizing.
"""

import pytest
from tests.stub_provider import StubDataProvider
from app.engines.scoring_engine import ScoringEngine
from app.engines.conviction_engine import ConvictionEngine
from app.models.conviction import BuyZone, ConvictionTier


def test_conviction_engine_single_emiten_bbri():
    provider = StubDataProvider()
    raw = provider.get_keystats("BBRI")
    assert raw is not None
    
    report = ScoringEngine.analyze_emiten(raw)
    assert report.buy_conviction is not None
    
    bc = report.buy_conviction
    assert bc.ticker == "BBRI"
    assert bc.total_checks_count == 10
    assert len(bc.checklist) == 10
    
    # Check multi-scenario targets
    sc = bc.scenarios
    assert sc.current_price == raw.current_price
    assert sc.bear_case_price <= sc.base_case_price
    assert sc.base_case_price <= sc.bull_case_price
    assert sc.risk_to_reward_ratio >= 0
    assert sc.buy_zone in [BuyZone.STRONG_ACCUMULATION, BuyZone.MODERATE_BUY, BuyZone.FAIR_HOLD]
    
    # Check position sizing advice
    ps = bc.position_sizing
    assert ps.max_portfolio_allocation_pct >= 10.0
    assert ps.take_profit_1 == sc.base_case_price
    assert ps.take_profit_2 == sc.bull_case_price
    assert ps.stop_loss_invalidation < sc.current_price


def test_multi_scenario_consistency_across_all_emitens():
    provider = StubDataProvider()
    tickers = provider.list_all_tickers()
    
    for ticker in tickers:
        raw = provider.get_keystats(ticker)
        assert raw is not None
        
        report = ScoringEngine.analyze_emiten(raw)
        assert report.buy_conviction is not None
        
        bc = report.buy_conviction
        sc = bc.scenarios
        # Fundamental hierarchy invariant: Bear <= Base <= Bull
        assert sc.bear_case_price <= sc.base_case_price, f"{ticker}: Bear ({sc.bear_case_price}) > Base ({sc.base_case_price})"
        assert sc.base_case_price <= sc.bull_case_price, f"{ticker}: Base ({sc.base_case_price}) > Bull ({sc.bull_case_price})"
        
        # 10 checklist items invariant
        assert len(bc.checklist) == 10
        assert 0 <= bc.passed_checks_count <= 10
        assert 0.0 <= bc.conviction_score <= 100.0


def test_checklist_criteria_validation():
    provider = StubDataProvider()
    raw_bbca = provider.get_keystats("BBCA")
    assert raw_bbca is not None
    
    report = ScoringEngine.analyze_emiten(raw_bbca)
    bc = report.buy_conviction
    assert bc is not None
    
    check_ids = [chk.id for chk in bc.checklist]
    expected_ids = [
        "chk_eps_growth",
        "chk_roe",
        "chk_cfo_quality",
        "chk_valuation",
        "chk_solvency",
        "chk_accounting",
        "chk_fcf",
        "chk_dividend",
        "chk_margin",
        "chk_mos"
    ]
    for exp_id in expected_ids:
        assert exp_id in check_ids
