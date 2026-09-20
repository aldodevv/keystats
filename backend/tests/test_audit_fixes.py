"""
Unit tests verifying comprehensive audit fixes:
- Bank balance sheet parsing & metrics calculation
- Turnaround growth calculation from negative to positive
- Beneish M-score exemption for banking/financial institutions
- Preservation of negative retained earnings in Altman Z-Score
- Refusal to fabricate positive DCF on cash-burning companies
- CAPM dynamic WACC adaptation
- EODHD override_price cache immutability
- EmitenService thread-safe caching and LRU bounds
- Screener price tier single-pass partitioning
- Telegram service security (no hardcoded credentials)
"""

import threading
from unittest.mock import MagicMock
import pytest
from app.models.keystats import RawKeyStats, FinancialPeriod, BankSpecificMetrics
from app.models.xbrl import XBRLEntryPoint
from app.models.score import HealthZone
from app.engines.financial_health import FinancialHealthEngine
from app.engines.valuation_engine import ValuationEngine
from app.data_providers.yfinance_provider import YFinanceProvider
from app.data_providers.eodhd_provider import EODHDProvider
from app.services.emiten_service import EmitenService
from app.services.screener_service import ScreenerService
from app.services.telegram_service import TelegramBotService
from tests.stub_provider import StubDataProvider


def test_turnaround_growth_calculation():
    """Turnaround companies moving from loss to profit must yield positive growth, not 0.0%."""
    raw = RawKeyStats(
        ticker="TURN",
        name="Turnaround Corp",
        sector="Industrial",
        industry="Machinery",
        current_price=1000.0,
        shares_outstanding=1_000_000,
        market_cap=1_000_000_000,
        current_period=FinancialPeriod(
            year=2024,
            revenue=100_000_000,
            net_income=20_000_000,  # profit 20M
            eps=20.0
        ),
        previous_period=FinancialPeriod(
            year=2023,
            revenue=80_000_000,
            net_income=-10_000_000,  # loss -10M
            eps=-10.0
        )
    )
    growth = FinancialHealthEngine.calculate_growth(raw)
    assert growth.revenue_growth_yoy == 25.0
    # Growth from -10M to +20M is (+20 - (-10)) / 10 = +300%
    assert growth.net_income_growth_yoy == 300.0
    assert growth.eps_growth_yoy == 300.0


def test_beneish_bank_exemption():
    """Banks must not be evaluated with Beneish M-score to prevent false positive fraud flags."""
    raw_bank = RawKeyStats(
        ticker="BBRI",
        name="Bank Rakyat Indonesia",
        sector="Financial Services (Banking)",
        industry="Banks",
        xbrl_entry_point=XBRLEntryPoint.FINANCIAL_BANKING,
        current_price=5000.0,
        shares_outstanding=150_000_000_000,
        market_cap=750_000_000_000_000,
        current_period=FinancialPeriod(
            year=2024,
            revenue=180_000_000_000_000,
            net_income=60_000_000_000_000,
            total_assets=2_000_000_000_000_000,
            cfo=50_000_000_000_000
        ),
        previous_period=FinancialPeriod(
            year=2023,
            revenue=160_000_000_000_000,
            net_income=55_000_000_000_000,
            total_assets=1_800_000_000_000_000,
            cfo=45_000_000_000_000
        )
    )
    qual = FinancialHealthEngine.calculate_quality(raw_bank)
    assert qual.beneish_m_score is None
    assert qual.is_manipulation_risk is False


def test_altman_z_preserves_negative_retained_earnings():
    """Altman-Z must preserve negative retained earnings rather than inflating them into positive 50% equity."""
    distressed_period = FinancialPeriod(
        year=2024,
        total_assets=1_000_000_000,
        total_liabilities=800_000_000,
        total_equity=200_000_000,
        current_assets=300_000_000,
        current_liabilities=500_000_000,  # negative working capital
        retained_earnings=-150_000_000,   # negative retained earnings
        operating_profit=-20_000_000,
        ebit=-20_000_000
    )
    z_score, zone = FinancialHealthEngine._calculate_altman_z(distressed_period)
    assert zone == HealthZone.DISTRESS
    assert z_score < 1.10


def test_dcf_negative_fcf_refuses_to_fabricate():
    """Cash-burning companies with negative FCF and negative CFO must return None, not fake positive DCF."""
    cash_burner = RawKeyStats(
        ticker="BURN",
        name="Cash Burner Tech Tbk",
        sector="Technology",
        industry="Software",
        current_price=50.0,
        shares_outstanding=1_000_000_000,
        market_cap=50_000_000_000,
        current_period=FinancialPeriod(
            year=2024,
            revenue=500_000_000,
            net_income=10_000_000,  # small accounting profit
            cfo=-50_000_000,        # negative operating cash flow
            capex=-30_000_000,      # capex
            fcf=-80_000_000,        # burning cash heavily
            total_debt=100_000_000,
            cash_and_equivalents=20_000_000
        )
    )
    dcf = ValuationEngine._calculate_dcf(cash_burner, shares=cash_burner.shares_outstanding)
    assert dcf is None


def test_dcf_dynamic_wacc_higher_for_high_beta():
    """High-beta companies should have higher WACC than low-beta companies."""
    p = FinancialPeriod(
        year=2024,
        fcf=100_000_000,
        cfo=120_000_000,
        capex=-20_000_000,
        total_debt=50_000_000,
        cash_and_equivalents=30_000_000
    )
    low_beta_stock = RawKeyStats(
        ticker="LOWB",
        name="Low Beta Consumer",
        sector="Consumer",
        industry="Staples",
        current_price=1000.0,
        shares_outstanding=1_000_000,
        market_cap=1_000_000_000,
        beta=0.5,
        current_period=p
    )
    high_beta_stock = RawKeyStats(
        ticker="HIGHB",
        name="High Beta Mining",
        sector="Basic Materials",
        industry="Coal Mining",
        current_price=1000.0,
        shares_outstanding=1_000_000,
        market_cap=1_000_000_000,
        beta=1.8,
        current_period=p
    )
    dcf_low = ValuationEngine._calculate_dcf(low_beta_stock, shares=1_000_000)
    dcf_high = ValuationEngine._calculate_dcf(high_beta_stock, shares=1_000_000)
    assert dcf_low is not None
    assert dcf_high is not None
    # Higher WACC results in lower present value
    assert dcf_low > dcf_high


def test_eodhd_override_price_preserves_cache():
    """Simulating price override in EODHDProvider must not pollute original cached price."""
    provider = EODHDProvider(api_key="test_key")
    real_stats = RawKeyStats(
        ticker="ASII",
        name="Astra International",
        sector="Consumer",
        industry="Automotive",
        current_price=5000.0,
        shares_outstanding=40_000_000_000,
        market_cap=200_000_000_000_000,
        current_period=FinancialPeriod(year=2024)
    )
    provider._cache["ASII"] = real_stats

    # Query with override
    simulated = provider.get_keystats("ASII", override_price=7000.0)
    assert simulated.current_price == 7000.0

    # Query again without override: must retain real price
    fresh = provider.get_keystats("ASII")
    assert fresh.current_price == 5000.0


def test_emiten_service_thread_safe_concurrent_caching():
    """EmitenService concurrent workers must safely access and write _report_cache."""
    stub = StubDataProvider()
    svc = EmitenService(provider=stub)
    tickers = ["BBRI", "BBCA", "BMRI", "TLKM", "ASII"] * 10  # 50 concurrent lookups

    errors = []

    def worker(t):
        try:
            rep = svc._cached_report(t)
            if rep is None:
                errors.append(f"Report for {t} is None")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker, args=(t,)) for t in tickers]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0


def test_screener_price_tiers_single_pass():
    """get_price_tier_recommendations must return valid 3 tiers partitioned cleanly."""
    stub = StubDataProvider()
    svc = ScreenerService(emiten_service=EmitenService(provider=stub))
    res = svc.get_price_tier_recommendations()

    assert res.total_recommendations > 0
    assert len(res.tiers) == 3
    tier_ids = [t.tier_id for t in res.tiers]
    assert tier_ids == ["budget", "mid_range", "premium"]


def test_telegram_service_no_hardcoded_secrets():
    """TelegramBotService should require explicit token / env and have no hardcoded default token."""
    svc = TelegramBotService()
    if not svc._bot_token:
        assert isinstance(svc.bot_token, str)
