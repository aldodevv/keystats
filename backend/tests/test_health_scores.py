"""
Unit tests for Financial Health (Piotroski F, Altman Z, DuPont ROE, OJK Banking Metrics, and XBRL Taxonomy).
"""

import pytest
from app.engines.financial_health import FinancialHealthEngine
from app.engines.profitability_engine import ProfitabilityEngine
from app.engines.sector_bank_engine import SectorBankEngine
from app.models.keystats import RawKeyStats, FinancialPeriod, BankSpecificMetrics
from app.models.xbrl import XBRLEntryPoint
from app.models.score import HealthZone


def test_piotroski_f_score_perfect_nine():
    # Setup periods where all 9 criteria improve
    prev = FinancialPeriod(
        year=2023,
        revenue=100.0,
        gross_profit=40.0,
        operating_profit=20.0,
        net_income=10.0,
        total_assets=100.0,
        current_assets=50.0,
        current_liabilities=30.0,
        long_term_debt=20.0,
        cfo=12.0,
        shares_outstanding=10.0
    )
    curr = FinancialPeriod(
        year=2024,
        revenue=120.0,          # rev up
        gross_profit=54.0,      # GPM 45% vs 40% (improves)
        operating_profit=25.0,
        net_income=15.0,        # ROA 12.5% vs 10% (improves)
        total_assets=120.0,     # Asset turn 1.0 vs 1.0 (same/better)
        current_assets=70.0,    # Current ratio 70/35 = 2.0 vs 50/30 = 1.67 (improves)
        current_liabilities=35.0,
        long_term_debt=18.0,    # Debt ratio 18/120 = 0.15 vs 20/100 = 0.20 (improves)
        cfo=20.0,               # CFO > Net Income (improves)
        shares_outstanding=10.0 # No dilution
    )
    raw = RawKeyStats(
        ticker="PERF",
        name="Perfect Stock Tbk",
        current_price=100.0,
        shares_outstanding=10.0,
        market_cap=1000.0,
        current_period=curr,
        previous_period=prev
    )
    
    qual = FinancialHealthEngine.calculate_quality(raw)
    assert qual.piotroski_f_score == 9
    assert qual.cfo_to_net_income == pytest.approx(1.33, rel=1e-2)


def test_dupont_roe_identity():
    # ROE = Net Margin * Asset Turnover * Equity Multiplier
    # (15/100) * (100/200) * (200/50) = 0.15 * 0.5 * 4 = 0.30 (30%)
    raw = RawKeyStats(
        ticker="DUPONT",
        name="DuPont Test Tbk",
        current_price=100.0,
        shares_outstanding=1.0,
        market_cap=100.0,
        current_period=FinancialPeriod(
            year=2024,
            revenue=100.0,
            gross_profit=40.0,
            operating_profit=20.0,
            net_income=15.0,
            total_assets=200.0,
            total_equity=50.0,
            current_liabilities=50.0
        )
    )
    prof = ProfitabilityEngine.calculate(raw)
    assert prof.roe == 30.0
    assert prof.dupont_net_margin == 0.15
    assert prof.dupont_asset_turnover == 0.5
    assert prof.dupont_equity_multiplier == 4.0
    # Identity test: Net Margin * Asset Turn * Eq Mult * 100 == ROE
    calculated_roe = prof.dupont_net_margin * prof.dupont_asset_turnover * prof.dupont_equity_multiplier * 100
    assert pytest.approx(calculated_roe, rel=1e-3) == prof.roe


def test_growth_and_cagr_calculation():
    p2021 = FinancialPeriod(year=2021, revenue=100.0, net_income=10.0, eps=10.0)
    p2022 = FinancialPeriod(year=2022, revenue=110.0, net_income=12.0, eps=12.0)
    p2023 = FinancialPeriod(year=2023, revenue=125.0, net_income=15.0, eps=15.0)
    p2024 = FinancialPeriod(year=2024, revenue=150.0, net_income=20.0, eps=20.0)
    
    raw = RawKeyStats(
        ticker="GROWTH",
        name="Growth Co Tbk",
        current_price=200.0,
        shares_outstanding=1.0,
        market_cap=200.0,
        current_period=p2024,
        previous_period=p2023,
        historical_periods=[p2023, p2022, p2021]
    )
    
    growth = FinancialHealthEngine.calculate_growth(raw)
    assert growth.revenue_growth_yoy == pytest.approx(20.0, rel=1e-2)
    assert growth.net_income_growth_yoy == pytest.approx(33.33, rel=1e-2)
    assert growth.eps_growth_yoy == pytest.approx(33.33, rel=1e-2)
    assert growth.eps_current == 20.0
    assert growth.revenue_current == 150.0
    assert growth.revenue_cagr_3y == pytest.approx(14.47, rel=1e-2)
    assert growth.eps_cagr_3y == pytest.approx(25.99, rel=1e-2)
    assert len(growth.revenue_history) == 4
    assert len(growth.eps_history) == 4


def test_ojk_banking_metrics_and_branching():
    # Setup BBCA bank emiten with OJK banking metrics
    raw_bank = RawKeyStats(
        ticker="BBCA",
        name="PT Bank Central Asia Tbk",
        sector="Financials",
        industry="Banking",
        xbrl_entry_point=XBRLEntryPoint.FINANCIAL_BANKING,
        current_price=10250.0,
        shares_outstanding=123_275_050_000,
        market_cap=1_263_569_262_500_000,
        current_period=FinancialPeriod(
            year=2024,
            filing_date="2025-01-25",
            xbrl_entry_point=XBRLEntryPoint.FINANCIAL_BANKING,
            revenue=108_250_000_000_000,
            gross_profit=82_100_000_000_000,
            operating_profit=66_800_000_000_000,
            net_income=54_800_000_000_000,
            eps=444.53,
            total_assets=1_449_300_000_000_000,
            total_liabilities=1_180_000_000_000_000,
            total_equity=269_300_000_000_000,
            interest_income=96_500_000_000_000,
            net_interest_income=82_100_000_000_000,
            earning_assets=1_380_000_000_000_000,
            total_loans=877_000_000_000_000,
            deposits_dpk=1_130_000_000_000_000,
            casa_deposits=926_600_000_000_000,
            regulatory_capital=260_000_000_000_000,
            risk_weighted_assets=890_000_000_000_000
        ),
        bank_metrics=BankSpecificMetrics(
            car=29.2,
            npl_gross=1.8,
            npl_net=0.4,
            nim=5.8,
            bopo=48.2,
            ldr=77.6,
            casa=82.0,
            cost_of_credit=0.3
        )
    )
    
    # 1. Evaluate Solvency for Bank -> Altman Z is branched to safe zone
    solv = FinancialHealthEngine.calculate_solvency(raw_bank)
    assert solv.altman_zone == HealthZone.SAFE
    assert solv.altman_z_score >= 3.0
    
    # 2. SectorBankEngine calculates exact OJK benchmarks
    bank_eval = SectorBankEngine.evaluate_bank(raw_bank)
    assert bank_eval["nim"] == 5.8
    assert bank_eval["car"] == 29.2
    assert bank_eval["npl_gross"] == 1.8
    assert bank_eval["bopo"] == 48.2
    assert bank_eval["casa"] == 82.0
    assert bank_eval["bank_health_score"] >= 80.0
    assert len(bank_eval["bank_strengths"]) >= 3


def test_analysis_pipeline_over_fixture_universe():
    """Validates the scoring pipeline against deterministic test fixtures (no live source)."""
    from tests.stub_provider import StubDataProvider
    from app.engines.scoring_engine import ScoringEngine

    provider = StubDataProvider()
    tickers = provider.list_all_tickers()
    assert len(tickers) >= 5

    for t in tickers:
        raw = provider.get_keystats(t)
        assert raw is not None
        assert raw.current_period.eps > 0
        assert raw.current_period.revenue > 0
        assert raw.current_period.net_income > 0
        assert raw.current_period.filing_date is not None
        assert raw.previous_period is not None
        assert len(raw.historical_periods) >= 3

        report = ScoringEngine.analyze_emiten(raw)
        assert report.eps > 0
        assert report.revenue > 0
        assert report.net_income > 0


def test_institutional_provider_uses_free_yfinance_by_default(monkeypatch):
    """
    With no licensed keys set, the provider must still be usable via the free public
    Yahoo Finance source (yfinance). It only fails loudly when even yfinance is
    unavailable — it must never fabricate data.
    """
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    from app.data_providers.institutional_provider import (
        InstitutionalDataProvider,
        DataSourceNotConfiguredError,
    )

    provider = InstitutionalDataProvider(sectors_api_key="", eodhd_api_key="demo")

    # yfinance is a free, keyless source and should keep the provider configured.
    assert provider.is_configured is True

    # If yfinance is unavailable (e.g. library missing), the provider must fail loudly
    # rather than fabricate data.
    provider.yfinance = None

    class _NoSources(InstitutionalDataProvider):
        def _configured_sources(self):
            return []

    empty = _NoSources(sectors_api_key="", eodhd_api_key="demo")
    assert empty.is_configured is False
    with pytest.raises(DataSourceNotConfiguredError):
        empty.get_keystats("BBRI")
    with pytest.raises(DataSourceNotConfiguredError):
        empty.list_all_tickers()
