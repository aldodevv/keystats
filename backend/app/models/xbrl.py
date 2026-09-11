"""
Standard XBRL Taxonomy Models and Line-Item Normalization for IDX Emitens.
Implements standardized entry points (General Industry, Banking, Property, Mining/Energy, Infrastructure)
and eliminates fragile line mapping in favor of deterministic XBRL element extraction.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class XBRLEntryPoint(str, Enum):
    GENERAL_INDUSTRY = "GeneralIndustry"
    FINANCIAL_BANKING = "FinancialServicesBank"
    FINANCIAL_NON_BANK = "FinancialServicesNonBank"
    PROPERTY_REAL_ESTATE = "PropertyRealEstate"
    MINING_ENERGY = "MiningEnergy"
    INFRASTRUCTURE = "Infrastructure"


class XBRLTaxonomyConcept(BaseModel):
    tag: str
    standard_label: str
    indonesian_label: str
    statement_type: str  # balance_sheet, income_statement, cash_flow, bank_regulatory
    description: Optional[str] = None


class XBRLTaxonomyRegistry:
    """
    Standard XBRL concept mappings based on IDX (Bursa Efek Indonesia) & OJK taxonomies.
    """
    
    # 1. Income Statement Concepts
    REVENUE = [
        "RevenueFromContractsWithCustomers",
        "Revenues",
        "SalesRevenueGoodsNet",
        "TotalRevenue",
        "OperatingRevenue",
        "InterestIncome",
        "GrossIncomeBank"
    ]
    
    INTEREST_INCOME = [
        "InterestIncome",
        "InterestAndSyariahIncome",
        "GrossInterestIncome"
    ]
    
    INTEREST_EXPENSE = [
        "InterestExpense",
        "InterestAndSyariahExpense",
        "BebanBunga"
    ]
    
    NET_INTEREST_INCOME = [
        "NetInterestIncome",
        "NetInterestAndSyariahIncome",
        "PendapatanBungaBersih"
    ]
    
    GROSS_PROFIT = [
        "GrossProfit",
        "NetInterestIncome",
        "GrossOperatingIncome"
    ]
    
    OPERATING_PROFIT = [
        "ProfitLossFromOperatingActivities",
        "OperatingIncome",
        "OperatingProfit",
        "OperatingProfitBank"
    ]
    
    OPERATING_EXPENSE = [
        "OperatingExpenses",
        "GeneralAndAdministrativeExpense",
        "BebanOperasional"
    ]
    
    EBIT = [
        "EarningsBeforeInterestAndTaxes",
        "OperatingIncome",
        "ProfitBeforeTaxAndInterest"
    ]
    
    EBITDA = [
        "EarningsBeforeInterestTaxesDepreciationAmortization",
        "EBITDA",
        "OperatingProfitPlusDepreciation"
    ]
    
    NET_INCOME = [
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLossForPeriod",
        "NetIncome",
        "NetIncomeLoss"
    ]
    
    EPS = [
        "BasicEarningsLossPerShare",
        "EarningsPerShare",
        "EPS"
    ]
    
    # 2. Balance Sheet Concepts
    TOTAL_ASSETS = [
        "Assets",
        "TotalAssets",
        "JumlahAset"
    ]
    
    CURRENT_ASSETS = [
        "CurrentAssets",
        "TotalCurrentAssets",
        "JumlahAsetLancar"
    ]
    
    CASH_EQUIVALENTS = [
        "CashAndCashEquivalents",
        "CashAndBankBalances",
        "KasDanSetaraKas"
    ]
    
    TRADE_RECEIVABLES = [
        "TradeReceivablesNet",
        "AccountsReceivable",
        "PiutangUsaha"
    ]
    
    INVENTORIES = [
        "Inventories",
        "Persediaan"
    ]
    
    TOTAL_LIABILITIES = [
        "Liabilities",
        "TotalLiabilities",
        "JumlahLiabilitas"
    ]
    
    CURRENT_LIABILITIES = [
        "CurrentLiabilities",
        "TotalCurrentLiabilities",
        "JumlahLiabilitasJangkaPendek"
    ]
    
    SHORT_TERM_DEBT = [
        "ShortTermBorrowings",
        "CurrentPortionOfLongTermDebt",
        "PinjamanJangkaPendek"
    ]
    
    LONG_TERM_DEBT = [
        "LongTermBorrowings",
        "LongTermDebtNet",
        "PinjamanJangkaPanjang"
    ]
    
    TOTAL_DEBT = [
        "TotalDebt",
        "TotalBorrowings",
        "JumlahUtangBerbunga"
    ]
    
    TOTAL_EQUITY = [
        "EquityAttributableToOwnersOfParent",
        "TotalEquity",
        "JumlahEkuitas"
    ]
    
    RETAINED_EARNINGS = [
        "RetainedEarnings",
        "AppropriatedRetainedEarnings",
        "SaldoLaba"
    ]
    
    # 3. Bank-Specific XBRL Concepts (OJK & BI Reporting Standards)
    BANK_EARNING_ASSETS = [
        "EarningAssets",
        "ProductiveAssets",
        "AsetProduktif"
    ]
    
    BANK_GROSS_LOANS = [
        "LoansAndAdvancesGross",
        "TotalLoansToCustomers",
        "KreditDiberikanGross"
    ]
    
    BANK_NPL_GROSS_AMOUNT = [
        "NonPerformingLoansGross",
        "ImpairedLoansGross",
        "KreditBermasalahGross"
    ]
    
    BANK_NPL_NET_AMOUNT = [
        "NonPerformingLoansNet",
        "ImpairedLoansNet",
        "KreditBermasalahNet"
    ]
    
    BANK_CUSTOMER_DEPOSITS_DPK = [
        "DepositsFromCustomers",
        "ThirdPartyFunds",
        "DanaPihakKetiga"
    ]
    
    BANK_CASA_DEPOSITS = [
        "DemandAndSavingsDeposits",
        "CurrentAccountsAndSavingsAccounts",
        "GiroDanTabungan"
    ]
    
    BANK_REGULATORY_CAPITAL = [
        "TotalRegulatoryCapital",
        "Tier1AndTier2Capital",
        "ModalRegulasi"
    ]
    
    BANK_RWA_ATMR = [
        "RiskWeightedAssets",
        "AktivaTertimbangMenurutRisiko"
    ]
    
    BANK_LOAN_LOSS_PROVISION = [
        "AllowanceForImpairmentLossesLoans",
        "CKPNKredit",
        "ProvisionForCreditLosses"
    ]
    
    # 4. Cash Flow Concepts
    CFO = [
        "CashFlowsFromUsedInOperatingActivities",
        "NetCashFromOperatingActivities",
        "ArusKasDariAktivitasOperasi"
    ]
    
    CAPEX = [
        "PaymentsForPropertyPlantAndEquipment",
        "CapitalExpenditures",
        "PerolehanAsetTetap"
    ]
    
    DIVIDENDS_PAID = [
        "DividendsPaid",
        "PaymentsOfDividends",
        "PembayaranDividen"
    ]
