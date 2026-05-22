"""
Commission Tracking Agent
LangGraph-based agent for tracking placement fees, invoicing, payment follow-ups,
and revenue forecasting.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Annotated, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base_agent import AgentState, BaseAgent

KAFKA_TOPIC_COMMISSION_EARNED = "commission.earned"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CommissionModel(str, Enum):
    PERCENTAGE_FIRST_SALARY = "percentage_of_first_salary"
    FLAT_FEE = "flat_fee"
    MONTHLY_RETAINER = "monthly_retainer"
    SUCCESS_FEE = "success_fee"

class PaymentStatus(str, Enum):
    PENDING_INVOICE = "pending_invoice"
    INVOICE_SENT = "invoice_sent"
    PARTIAL_PAYMENT = "partial_payment"
    PAID = "paid"
    OVERDUE = "overdue"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class CommissionState(TypedDict, total=False):
    """State for the CommissionTrackingAgent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    placement: Optional[Dict[str, Any]]
    commission_record: Optional[Dict[str, Any]]
    payment_status: Optional[str]
    invoice_sent: bool
    reminder_sent: bool
    revenue_report: Optional[Dict[str, Any]]
    forecast: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def calculate_commission(
    placement: Dict[str, Any],
    commission_model: str = CommissionModel.PERCENTAGE_FIRST_SALARY.value,
) -> Dict[str, Any]:
    """
    Calculate the commission amount for a placement.

    Args:
        placement: Dict with candidate_ctc_annual, notice_period, role, client_company.
        commission_model: One of the CommissionModel enum values.

    Returns:
        Dict with gross_commission_inr, net_commission_inr, model_used, calculation_breakdown.
    """
    ctc_annual = float(placement.get("candidate_ctc_annual", 0))
    ctc_monthly = ctc_annual / 12

    if commission_model == CommissionModel.PERCENTAGE_FIRST_SALARY.value:
        # Standard: 8.33% of annual CTC = 1 month salary
        gross = ctc_monthly
        model_detail = f"8.33% of annual CTC (₹{ctc_annual:,.0f}) = 1 month salary"
    elif commission_model == CommissionModel.FLAT_FEE.value:
        flat = float(placement.get("agreed_flat_fee", 50000))
        gross = flat
        model_detail = f"Agreed flat fee: ₹{flat:,.0f}"
    elif commission_model == CommissionModel.MONTHLY_RETAINER.value:
        monthly = float(placement.get("monthly_retainer_amount", 25000))
        months = int(placement.get("retainer_months", 3))
        gross = monthly * months
        model_detail = f"Monthly retainer ₹{monthly:,.0f} × {months} months"
    else:  # success fee
        success_pct = float(placement.get("success_fee_pct", 10)) / 100
        gross = ctc_annual * success_pct
        model_detail = f"{success_pct:.0%} of annual CTC"

    gst_rate = 0.18
    gst_amount = gross * gst_rate
    net = gross + gst_amount

    return {
        "placement_id": placement.get("placement_id", str(uuid.uuid4())),
        "commission_model": commission_model,
        "gross_commission_inr": round(gross, 2),
        "gst_18_pct_inr": round(gst_amount, 2),
        "net_commission_inr": round(net, 2),
        "calculation_breakdown": model_detail,
        "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "calculated_at": datetime.utcnow().isoformat(),
    }


@tool
def track_payment_status(commission_id: str) -> Dict[str, Any]:
    """
    Retrieve the current payment status for a commission record.

    Args:
        commission_id: Unique identifier for the commission record.

    Returns:
        Dict with status, amount_paid, amount_pending, due_date, days_overdue.
    """
    # In production: queries PostgreSQL commissions table
    return {
        "commission_id": commission_id,
        "status": PaymentStatus.PENDING_INVOICE.value,
        "amount_paid_inr": 0.0,
        "amount_pending_inr": 0.0,
        "due_date": None,
        "days_overdue": 0,
        "payment_history": [],
        "last_checked": time.time(),
    }


@tool
def send_invoice_reminder(
    commission: Dict[str, Any],
    reminder_number: int = 1,
) -> Dict[str, Any]:
    """
    Generate and send an invoice reminder to the client.

    Args:
        commission: Commission record with client contact and amount details.
        reminder_number: Reminder sequence number (1=gentle, 2=firm, 3=final).

    Returns:
        Dict with reminder_sent (bool), message_type, scheduled_followup_date.
    """
    client = commission.get("client", {})
    amount = commission.get("net_commission_inr", 0)
    placement_name = commission.get("candidate_name", "the candidate")
    due_date = commission.get("due_date", "as agreed")

    tone_map = {
        1: ("gentle", f"Hi {client.get('name', 'there')},\n\nJust a friendly reminder that our invoice for the placement of {placement_name} (₹{amount:,.0f}) is due on {due_date}. Please let us know if you need any documentation.\n\nThanks,"),
        2: ("firm", f"Hi {client.get('name', 'there')},\n\nThis is a follow-up regarding our outstanding invoice for ₹{amount:,.0f} for {placement_name}. The payment was due on {due_date}. Please process this at your earliest convenience.\n\nRegards,"),
        3: ("final", f"Dear {client.get('name', 'there')},\n\nThis is a final notice for our overdue invoice of ₹{amount:,.0f} for {placement_name} (due: {due_date}). Please arrange payment within 7 days to avoid escalation.\n\nSincerely,"),
    }

    tone, message = tone_map.get(reminder_number, tone_map[1])
    next_reminder_days = [7, 14, None][min(reminder_number - 1, 2)]
    next_date = (datetime.utcnow() + timedelta(days=next_reminder_days)).isoformat() if next_reminder_days else None

    return {
        "reminder_sent": True,
        "reminder_number": reminder_number,
        "tone": tone,
        "message_preview": message[:200],
        "client_email": client.get("email"),
        "next_reminder_date": next_date,
        "escalate_to_legal": reminder_number >= 3,
    }


@tool
def generate_revenue_report(
    placements: List[Dict[str, Any]],
    period_start: str,
    period_end: str,
) -> Dict[str, Any]:
    """
    Generate a revenue report for a specified time period.

    Args:
        placements: List of placement records with commission data.
        period_start: ISO date string for period start.
        period_end: ISO date string for period end.

    Returns:
        Dict with total_revenue, by_client, by_role, by_model, monthly_breakdown.
    """
    total_gross = sum(p.get("gross_commission_inr", 0) for p in placements)
    total_net = sum(p.get("net_commission_inr", 0) for p in placements)
    total_paid = sum(p.get("amount_paid_inr", 0) for p in placements)
    total_pending = total_net - total_paid

    by_client: Dict[str, float] = {}
    by_role: Dict[str, float] = {}
    by_model: Dict[str, float] = {}

    for p in placements:
        client = p.get("client_company", "Unknown")
        role = p.get("role", "Unknown")
        model = p.get("commission_model", "unknown")
        amt = p.get("net_commission_inr", 0)

        by_client[client] = round(by_client.get(client, 0) + amt, 2)
        by_role[role] = round(by_role.get(role, 0) + amt, 2)
        by_model[model] = round(by_model.get(model, 0) + amt, 2)

    return {
        "period": {"start": period_start, "end": period_end},
        "summary": {
            "total_placements": len(placements),
            "total_gross_revenue_inr": round(total_gross, 2),
            "total_net_revenue_inr": round(total_net, 2),
            "total_paid_inr": round(total_paid, 2),
            "total_pending_inr": round(total_pending, 2),
            "collection_rate_pct": round(total_paid / max(1, total_net) * 100, 1),
        },
        "by_client": dict(sorted(by_client.items(), key=lambda x: x[1], reverse=True)),
        "by_role": dict(sorted(by_role.items(), key=lambda x: x[1], reverse=True)),
        "by_commission_model": by_model,
        "avg_commission_per_placement": round(total_net / max(1, len(placements)), 2),
        "generated_at": datetime.utcnow().isoformat(),
    }


@tool
def forecast_revenue(
    pipeline_commissions: List[Dict[str, Any]],
    historical_collection_rate: float = 0.85,
) -> Dict[str, Any]:
    """
    Forecast future revenue from the current commission pipeline.

    Args:
        pipeline_commissions: List of pending/in-progress commission records.
        historical_collection_rate: Historical payment collection rate (0-1).

    Returns:
        Dict with expected_revenue at 30/60/90 day horizons and risk assessment.
    """
    total_pipeline = sum(c.get("net_commission_inr", 0) for c in pipeline_commissions)

    status_probability = {
        PaymentStatus.INVOICE_SENT.value: 0.8,
        PaymentStatus.PARTIAL_PAYMENT.value: 0.9,
        PaymentStatus.PENDING_INVOICE.value: 0.6,
        PaymentStatus.OVERDUE.value: 0.4,
        PaymentStatus.DISPUTED.value: 0.2,
    }

    weighted_expected = 0.0
    at_risk = 0.0
    for c in pipeline_commissions:
        status = c.get("payment_status", PaymentStatus.PENDING_INVOICE.value)
        prob = status_probability.get(status, 0.5)
        amount = c.get("net_commission_inr", 0)
        weighted_expected += amount * prob
        if prob < 0.5:
            at_risk += amount

    expected_30d = weighted_expected * 0.4
    expected_60d = weighted_expected * 0.7
    expected_90d = weighted_expected

    return {
        "pipeline_total_inr": round(total_pipeline, 2),
        "expected_revenue": {
            "30_days_inr": round(expected_30d, 2),
            "60_days_inr": round(expected_60d, 2),
            "90_days_inr": round(expected_90d, 2),
        },
        "at_risk_amount_inr": round(at_risk, 2),
        "at_risk_pct": round(at_risk / max(1, total_pipeline) * 100, 1),
        "historical_collection_rate": f"{historical_collection_rate:.0%}",
        "pipeline_count": len(pipeline_commissions),
        "forecast_generated_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CommissionTrackingAgent(BaseAgent):
    """
    LangGraph agent for commission calculation, payment tracking, and revenue reporting.

    Workflow:
        calculate_commission -> track_status -> send_reminder ->
        generate_report -> forecast_revenue_node -> END
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="CommissionTrackingAgent", **kwargs)
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(CommissionState)
        workflow.add_node("calculate_commission_node", self._node_calculate_commission)
        workflow.add_node("track_status_node", self._node_track_status)
        workflow.add_node("send_reminder_node", self._node_send_reminder)
        workflow.add_node("generate_report_node", self._node_generate_report)
        workflow.add_node("forecast_revenue_node", self._node_forecast_revenue)

        workflow.set_entry_point("calculate_commission_node")
        workflow.add_edge("calculate_commission_node", "track_status_node")
        workflow.add_edge("track_status_node", "send_reminder_node")
        workflow.add_edge("send_reminder_node", "generate_report_node")
        workflow.add_edge("generate_report_node", "forecast_revenue_node")
        workflow.add_edge("forecast_revenue_node", END)
        return workflow.compile()

    async def _node_calculate_commission(self, state: CommissionState) -> CommissionState:
        self.log_state_transition("START", "calculate_commission_node", list(state.keys()))
        placement = state.get("placement")
        if not placement:
            return {**state, "error": "No placement data provided"}

        model = placement.get("commission_model", CommissionModel.PERCENTAGE_FIRST_SALARY.value)
        commission = calculate_commission.invoke({
            "placement": placement,
            "commission_model": model,
        })

        try:
            self.publish_to_kafka(
                topic=KAFKA_TOPIC_COMMISSION_EARNED,
                payload={
                    "placement_id": commission["placement_id"],
                    "gross_commission_inr": commission["gross_commission_inr"],
                    "net_commission_inr": commission["net_commission_inr"],
                    "commission_model": model,
                    "client_company": placement.get("client_company"),
                    "candidate_name": placement.get("candidate_name"),
                    "role": placement.get("role"),
                },
            )
        except Exception as exc:
            self.logger.warning("Kafka publish for commission failed: %s", exc)

        return {**state, "commission_record": commission}

    async def _node_track_status(self, state: CommissionState) -> CommissionState:
        self.log_state_transition("calculate_commission_node", "track_status_node", list(state.keys()))
        commission = state.get("commission_record", {})
        commission_id = commission.get("placement_id", "")
        status_data = track_payment_status.invoke({"commission_id": commission_id})
        return {**state, "payment_status": status_data.get("status")}

    async def _node_send_reminder(self, state: CommissionState) -> CommissionState:
        self.log_state_transition("track_status_node", "send_reminder_node", list(state.keys()))
        status = state.get("payment_status", PaymentStatus.PENDING_INVOICE.value)
        commission = state.get("commission_record", {})
        placement = state.get("placement", {})

        send_reminder = status in [
            PaymentStatus.OVERDUE.value,
            PaymentStatus.INVOICE_SENT.value,
        ]

        if send_reminder:
            days_overdue = 0
            reminder_num = 2 if days_overdue > 14 else 1
            enriched_commission = {
                **commission,
                "client": placement.get("client_contact", {}),
                "candidate_name": placement.get("candidate_name", "the candidate"),
                "client_company": placement.get("client_company", ""),
            }
            result = send_invoice_reminder.invoke({
                "commission": enriched_commission,
                "reminder_number": reminder_num,
            })
            return {**state, "invoice_sent": True, "reminder_sent": result.get("reminder_sent", False)}

        return {**state, "invoice_sent": False, "reminder_sent": False}

    async def _node_generate_report(self, state: CommissionState) -> CommissionState:
        self.log_state_transition("send_reminder_node", "generate_report_node", list(state.keys()))
        commission = state.get("commission_record")
        placement = state.get("placement", {})

        placements_for_report = []
        if commission and placement:
            placements_for_report.append({
                **commission,
                "client_company": placement.get("client_company", ""),
                "role": placement.get("role", ""),
                "amount_paid_inr": 0.0,
            })

        now = datetime.utcnow()
        report = generate_revenue_report.invoke({
            "placements": placements_for_report,
            "period_start": (now - timedelta(days=30)).isoformat(),
            "period_end": now.isoformat(),
        })
        return {**state, "revenue_report": report}

    async def _node_forecast_revenue(self, state: CommissionState) -> CommissionState:
        self.log_state_transition("generate_report_node", "forecast_revenue_node", list(state.keys()))
        commission = state.get("commission_record")
        pipeline = []
        if commission:
            pipeline.append({
                **commission,
                "payment_status": state.get("payment_status", PaymentStatus.PENDING_INVOICE.value),
            })

        forecast = forecast_revenue.invoke({
            "pipeline_commissions": pipeline,
            "historical_collection_rate": 0.85,
        })
        return {**state, "forecast": forecast}

    async def run(
        self,
        task: str,
        placement: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Calculate, track, and report on a placement commission."""
        initial: CommissionState = {
            "messages": [],
            "task": task,
            "placement": placement,
            "commission_record": None,
            "payment_status": None,
            "invoice_sent": False,
            "reminder_sent": False,
            "revenue_report": None,
            "forecast": None,
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }
        final = await self._graph.ainvoke(initial)
        return {
            "commission_record": final.get("commission_record"),
            "payment_status": final.get("payment_status"),
            "invoice_sent": final.get("invoice_sent"),
            "reminder_sent": final.get("reminder_sent"),
            "revenue_report": final.get("revenue_report"),
            "forecast": final.get("forecast"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "track commission"),
            placement=meta.get("placement"),
        )
        return {**state, "result": result, "updated_at": time.time()}
