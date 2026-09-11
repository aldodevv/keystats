"""
Curated IDX (Bursa Efek Indonesia) ticker universe.

Yahoo Finance has no free "list every IDX symbol" endpoint, so BRIGHTS bundles a curated
list of *real* IDX ticker codes (LQ45 / IDX80 constituents plus other liquid, widely-held
emitens) to seed market-wide features (Top Picks, screener, market summary).

Important:
  - These are only ticker CODES — public identifiers, not fabricated financial data.
  - Every emiten's actual figures (price, fundamentals, ownership) are still fetched LIVE
    from the data source (Yahoo Finance) at query time. Nothing here is a mock number.
  - Tickers that fail to resolve live are simply skipped downstream, never invented.

You can override / extend this at runtime with the IDX_TICKER_UNIVERSE environment
variable (comma-separated codes, e.g. "BBRI,ASII,TLKM").
"""

import os
from typing import List

# Real IDX ticker codes (common stocks). Curated toward the most liquid / widely-followed
# names across sectors so market-wide analytics have meaningful coverage out of the box.
_DEFAULT_IDX_TICKERS: List[str] = [
    # Banks / Financials
    "BBRI", "BBCA", "BMRI", "BBNI", "BRIS", "BBTN", "BJBR", "BJTM", "ARTO", "BTPS",
    "PNBN", "BNGA", "MEGA", "BFIN", "AMAR",
    # Consumer / FMCG
    "UNVR", "ICBP", "INDF", "MYOR", "GGRM", "HMSP", "KLBF", "SIDO", "CPIN", "JPFA",
    "ULTJ", "ROTI", "MLBI", "AMRT", "MAPI", "MAPA", "ACES", "ERAA", "RALS", "LPPF",
    # Telco / Tech / Media
    "TLKM", "ISAT", "EXCL", "TOWR", "TBIG", "MTEL", "GOTO", "BUKA", "EMTK", "MNCN",
    "SCMA", "FREN", "DMMX",
    # Energy / Coal / Oil & Gas
    "ADRO", "PTBA", "ITMG", "PGAS", "MEDC", "HRUM", "INDY", "ELSA", "ADMR", "BUMI",
    "AKRA", "ENRG", "RAJA",
    # Metals / Mining
    "ANTM", "INCO", "TINS", "MDKA", "PSAB", "NCKL", "BRMS", "ARCI",
    # Basic Materials / Cement / Chemicals
    "SMGR", "INTP", "BRPT", "TPIA", "SMBR", "INKP", "TKIM", "ESSA", "AVIA",
    # Property / Construction / Infrastructure
    "BSDE", "CTRA", "SMRA", "PWON", "ASRI", "WIKA", "WSKT", "PTPP", "ADHI", "JSMR",
    "META", "CMNP",
    # Industrials / Autos / Conglomerates
    "ASII", "UNTR", "GJTL", "AUTO", "SRIL", "ARNA", "MARK",
    # Healthcare / Pharma
    "KAEF", "INAF", "MIKA", "SILO", "HEAL", "PRDA", "SAME",
    # Agri / Plantation
    "AALI", "LSIP", "SIMP", "DSNG", "TAPG", "SGRO", "BWPT",
    # Transportation / Logistics / Others
    "GIAA", "ASSA", "SMDR", "TMAS", "BIRD", "WEHA",
    # Poultry / Retail / Misc large caps
    "PANI", "AMMN", "BREN", "CUAN", "MBMA", "PTRO",
]


def get_idx_universe() -> List[str]:
    """
    Returns the IDX ticker universe. If IDX_TICKER_UNIVERSE env var is set, it fully
    overrides the bundled list; otherwise the curated default is used.
    """
    override = os.getenv("IDX_TICKER_UNIVERSE", "").strip()
    if override:
        codes = [c.strip().upper().replace(".JK", "") for c in override.split(",") if c.strip()]
        if codes:
            # De-duplicate while preserving order.
            seen = set()
            result = []
            for c in codes:
                if c not in seen:
                    seen.add(c)
                    result.append(c)
            return result
    return list(_DEFAULT_IDX_TICKERS)
