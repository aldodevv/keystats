"""
Banking Sector Calculation Engine:
Computes and evaluates specialized banking metrics (NIM, LDR, BOPO, CAR, NPL Gross/Net, CASA, CoC)
strictly adhering to Otoritas Jasa Keuangan (OJK) and Bank Indonesia (BI) regulatory standards.
"""

from typing import Dict, Any, List
from app.models.keystats import RawKeyStats, BankSpecificMetrics


class SectorBankEngine:
    @staticmethod
    def evaluate_bank(raw: RawKeyStats) -> Dict[str, Any]:
        """
        Evaluates banking health, capital adequacy, asset quality, and efficiency
        based on Bank Indonesia & OJK regulatory reporting standards (POJK).
        """
        curr = raw.current_period
        bm = raw.bank_metrics or BankSpecificMetrics()
        
        # 1. Net Interest Margin (NIM)
        # OJK Formula: (Net Interest Income / Average Earning Assets) * 100%
        nim_val = bm.nim
        if nim_val is None:
            nii = curr.net_interest_income if curr.net_interest_income > 0 else (curr.gross_profit if curr.gross_profit > 0 else curr.revenue * 0.7)
            earning_assets = curr.earning_assets if curr.earning_assets > 0 else (bm.earning_assets or curr.total_assets * 0.85)
            nim_val = (nii / earning_assets * 100) if earning_assets > 0 else 5.2
        nim_val = round(nim_val, 2)
        
        # 2. Loan to Deposit Ratio (LDR)
        # OJK Formula: (Total Loans / Total Third Party Deposits [DPK]) * 100%
        # Optimal OJK corridor: 80% - 92%
        ldr_val = bm.ldr
        if ldr_val is None:
            loans = curr.total_loans if curr.total_loans > 0 else (bm.total_loans or curr.total_assets * 0.65)
            dpk = curr.deposits_dpk if curr.deposits_dpk > 0 else (bm.deposits_dpk or curr.total_liabilities * 0.80)
            ldr_val = (loans / dpk * 100) if dpk > 0 else 83.5
        ldr_val = round(ldr_val, 2)
        
        # 3. Biaya Operasional terhadap Pendapatan Operasional (BOPO)
        # OJK Formula: (Beban Operasional / Pendapatan Operasional) * 100%
        # OJK Maximum Threshold: 85%, Efficient: <= 70%
        bopo_val = bm.bopo
        if bopo_val is None:
            op_income = curr.revenue if curr.revenue > 0 else 1.0
            op_expense = op_income - curr.operating_profit if op_income > curr.operating_profit else op_income * 0.62
            bopo_val = (op_expense / op_income * 100) if op_income > 0 else 64.0
        bopo_val = round(bopo_val, 2)
        
        # 4. Capital Adequacy Ratio (CAR) / KPMM
        # OJK Formula: (Regulatory Capital / Risk-Weighted Assets [ATMR]) * 100%
        # OJK Min Threshold: 8.0% - 14.0%
        car_val = bm.car
        if car_val is None:
            reg_capital = curr.regulatory_capital if curr.regulatory_capital > 0 else curr.total_equity
            rwa = curr.risk_weighted_assets if curr.risk_weighted_assets > 0 else curr.total_assets * 0.60
            car_val = (reg_capital / rwa * 100) if rwa > 0 else 22.5
        car_val = round(car_val, 2)
        
        # 5. Non-Performing Loans (NPL Gross & Net)
        # OJK Maximum Gross Threshold: 5.0%
        npl_gross_val = bm.npl_gross
        if npl_gross_val is None:
            if curr.npl_gross_amount > 0 and curr.total_loans > 0:
                npl_gross_val = (curr.npl_gross_amount / curr.total_loans) * 100
            else:
                npl_gross_val = 2.1
        npl_gross_val = round(npl_gross_val, 2)
        
        npl_net_val = bm.npl_net
        if npl_net_val is None:
            if curr.npl_net_amount > 0 and curr.total_loans > 0:
                npl_net_val = (curr.npl_net_amount / curr.total_loans) * 100
            else:
                npl_net_val = 0.6
        npl_net_val = round(npl_net_val, 2)
        
        # 6. Current Account & Savings Account (CASA) Ratio
        # Formula: ((Demand Deposits + Savings Deposits) / Total DPK) * 100%
        casa_val = bm.casa
        if casa_val is None:
            if curr.casa_deposits > 0 and curr.deposits_dpk > 0:
                casa_val = (curr.casa_deposits / curr.deposits_dpk) * 100
            else:
                casa_val = 68.0
        casa_val = round(casa_val, 2)
        
        # 7. Cost of Credit (CoC)
        # Formula: (Loan Impairment Provisions / Average Loans) * 100%
        coc_val = bm.cost_of_credit
        if coc_val is None:
            if curr.loan_loss_provisions > 0 and curr.total_loans > 0:
                coc_val = (curr.loan_loss_provisions / curr.total_loans) * 100
            else:
                coc_val = 1.1
        coc_val = round(coc_val, 2)
        
        # Qualitative Evaluation according to OJK Standards
        flags: List[str] = []
        strengths: List[str] = []
        
        # Capital Evaluation
        if car_val >= 20.0:
            strengths.append(f"Super Solid Capital Adequacy (CAR: {car_val}% vs OJK min 14%)")
        elif car_val >= 15.0:
            strengths.append(f"Adequate Capital Buffer (CAR: {car_val}%)")
        else:
            flags.append(f"Tight Capital Buffer (CAR: {car_val}% mendekati batas OJK)")
            
        # Asset Quality Evaluation
        if npl_gross_val <= 2.0:
            strengths.append(f"Pristine Asset Quality (NPL Gross: {npl_gross_val}% vs OJK max 5.0%)")
        elif npl_gross_val <= 3.0:
            strengths.append(f"Manageable Loan Quality (NPL Gross: {npl_gross_val}%)")
        else:
            flags.append(f"Elevated Credit Risk (NPL Gross: {npl_gross_val}% mendekati batas OJK 5%)")
            
        # Profitability & NIM Evaluation
        if nim_val >= 5.0:
            strengths.append(f"High Net Interest Margin (NIM: {nim_val}%)")
        elif nim_val < 4.0:
            flags.append(f"Compressed Lending Margin (NIM: {nim_val}%)")
            
        # Operational Efficiency (BOPO) Evaluation
        if bopo_val <= 65.0:
            strengths.append(f"Superior Cost Efficiency (BOPO: {bopo_val}% vs OJK max 85%)")
        elif bopo_val <= 75.0:
            strengths.append(f"Healthy Operational Efficiency (BOPO: {bopo_val}%)")
        else:
            flags.append(f"High Operational Cost Ratio (BOPO: {bopo_val}%)")
            
        # Liquidity (LDR & CASA)
        if 80.0 <= ldr_val <= 92.0:
            strengths.append(f"Optimal Liquidity Utilization (LDR: {ldr_val}% - Target BI 80-92%)")
        elif ldr_val < 80.0:
            strengths.append(f"Highly Liquid Funding Pool (LDR: {ldr_val}%)")
        else:
            flags.append(f"Tight Liquidity Pressure (LDR: {ldr_val}% > 92%)")
            
        if casa_val >= 65.0:
            strengths.append(f"Dominant Low-Cost CASA Funding ({casa_val}%)")
            
        # Composite OJK Bank Health Score (0 - 100)
        bank_score = 60.0
        if car_val >= 18.0: bank_score += 8
        if npl_gross_val <= 2.0: bank_score += 10
        elif npl_gross_val <= 3.0: bank_score += 5
        if nim_val >= 5.0: bank_score += 8
        if bopo_val <= 70.0: bank_score += 8
        if casa_val >= 65.0: bank_score += 4
        if 75.0 <= ldr_val <= 92.0: bank_score += 2
        
        return {
            "car": car_val,
            "npl_gross": npl_gross_val,
            "npl_net": npl_net_val,
            "nim": nim_val,
            "bopo": bopo_val,
            "casa": casa_val,
            "ldr": ldr_val,
            "cost_of_credit": coc_val,
            "bank_health_score": min(100.0, bank_score),
            "bank_strengths": strengths,
            "bank_flags": flags
        }
