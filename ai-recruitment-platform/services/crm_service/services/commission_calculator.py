"""Commission calculation and revenue tracking."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from common.config import settings
from common.logging import get_logger

logger = get_logger(__name__)


class CommissionModel(str, Enum):
    PERCENTAGE = "percentage"
    FLAT_FEE = "flat_fee"
    MONTHLY_RETAINER = "monthly_retainer"
    CONTRACT_MARGIN = "contract_margin"


@dataclass
class CommissionResult:
    gross_commission: float
    net_commission: float
    tax_amount: float
    commission_model: CommissionModel
    calculation_details: Dict[str, Any]


class CommissionCalculator:
    """Calculate recruitment commissions for various placement types."""

    GST_RATE = 0.18  # 18% GST in India

    def calculate_permanent_placement_fee(
        self,
        salary: float,
        percentage: float = None,
        include_gst: bool = True,
    ) -> float:
        """
        Standard India permanent placement: 1 month salary = 8.33% of annual CTC.
        Returns gross commission amount in INR.
        """
        pct = percentage or settings.default_permanent_commission_pct
        commission = (salary * pct) / 100
        if include_gst:
            commission = commission * (1 + self.GST_RATE)
        return round(commission, 2)

    def calculate_contract_fee(
        self,
        daily_rate: float,
        margin_percentage: float = None,
        working_days_per_month: int = 22,
    ) -> float:
        """
        Contract margin calculation.
        monthly_revenue = daily_rate * working_days * margin_pct / 100
        """
        margin = margin_percentage or settings.default_contract_margin_pct
        monthly_billing = daily_rate * working_days_per_month
        monthly_revenue = (monthly_billing * margin) / 100
        return round(monthly_revenue, 2)

    def calculate_c2h_fee(
        self,
        monthly_ctc: float,
        months_contract: int = 6,
        conversion_fee_months: int = 1,
        contract_margin_pct: float = None,
    ) -> Dict[str, float]:
        """
        C2H (Contract-to-Hire) fee structure.
        Returns dict with contract_revenue, conversion_fee, total_expected_revenue.
        """
        margin = contract_margin_pct or settings.default_contract_margin_pct
        monthly_margin = (monthly_ctc * margin) / 100
        contract_revenue = monthly_margin * months_contract
        conversion_fee = monthly_ctc * conversion_fee_months
        return {
            "contract_revenue": round(contract_revenue, 2),
            "conversion_fee": round(conversion_fee, 2),
            "total_expected_revenue": round(contract_revenue + conversion_fee, 2),
            "monthly_margin": round(monthly_margin, 2),
        }

    def estimate_monthly_revenue(self, pipeline_items: List[Dict[str, Any]]) -> Dict[str, float]:
        """Estimate monthly revenue from active pipeline."""
        total = 0.0
        by_stage = {}
        for item in pipeline_items:
            stage = item.get("stage", "unknown")
            probability = item.get("probability", 0) / 100
            expected_monthly = item.get("expected_monthly_revenue", 0) or 0
            expected = expected_monthly * probability
            total += expected
            by_stage[stage] = by_stage.get(stage, 0) + expected
        return {"total_expected": round(total, 2), "by_stage": {k: round(v, 2) for k, v in by_stage.items()}}

    def generate_invoice(
        self,
        placement: Dict[str, Any],
        our_company: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate invoice details for a placement."""
        import uuid
        from datetime import datetime, timezone, timedelta

        commission = placement.get("commission_amount", 0)
        gst = round(commission * self.GST_RATE, 2)
        total = round(commission + gst, 2)

        return {
            "invoice_number": f"INV-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}",
            "date": datetime.now(timezone.utc).isoformat(),
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "from": our_company,
            "to": {
                "company": placement.get("employer_name"),
                "gst_number": placement.get("employer_gst"),
            },
            "description": (
                f"Recruitment Fee for {placement.get('candidate_name')} "
                f"({placement.get('job_title')}) - "
                f"{placement.get('commission_percentage', 8.33)}% of "
                f"₹{placement.get('annual_salary', 0):,.0f} Annual CTC"
            ),
            "amount": commission,
            "gst_18pct": gst,
            "total_amount": total,
            "currency": "INR",
            "payment_terms": "Net 30",
            "bank_details": our_company.get("bank_details", {}),
        }
