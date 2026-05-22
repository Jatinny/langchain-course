"""
Lead Qualification Agent
LangGraph-based agent for researching, verifying, and scoring employer leads
to prioritize outreach efforts.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Annotated, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base_agent import AgentState, BaseAgent

KAFKA_TOPIC_EMPLOYER_QUALIFIED = "employer.qualified"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class LeadQualificationState(TypedDict, total=False):
    """State for the LeadQualificationAgent LangGraph workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    lead: Dict[str, Any]
    research_data: Optional[Dict[str, Any]]
    contact_verified: bool
    quality_score: Optional[Dict[str, Any]]
    priority_class: Optional[str]
    action_plan: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def research_company(company_name: str, website: Optional[str] = None) -> Dict[str, Any]:
    """
    Research a company's background, recent news, and hiring activities.

    Args:
        company_name: Name of the company to research.
        website: Company website URL (optional).

    Returns:
        Dict with recent_news, funding_stage, employee_growth, tech_stack,
        glassdoor_rating, and linkedin_followers.
    """
    # In production: calls news APIs, LinkedIn scraper, Crunchbase API
    return {
        "company_name": company_name,
        "website": website,
        "research_status": "pending",
        "data_sources": ["linkedin", "crunchbase", "news_api", "glassdoor"],
        "research_timestamp": time.time(),
    }


@tool
def check_hiring_activity(company_name: str, platform: str = "naukri.com") -> Dict[str, Any]:
    """
    Check current and historical hiring activity for a company.

    Args:
        company_name: Company to check.
        platform: Job board to check.

    Returns:
        Dict with active_job_count, roles_hiring_for, hiring_trend (up/down/stable),
        last_posting_date, avg_monthly_postings.
    """
    # In production: scrapes job boards and returns real data
    return {
        "company_name": company_name,
        "platform": platform,
        "active_job_count": 0,
        "roles_hiring_for": [],
        "hiring_trend": "unknown",
        "last_posting_date": None,
        "avg_monthly_postings": 0,
        "check_timestamp": time.time(),
    }


@tool
def verify_vendor_friendliness(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify whether a company is genuinely vendor-friendly vs. direct hiring only.

    Args:
        company_data: Company information including JD samples and LinkedIn data.

    Returns:
        Dict with verdict, evidence, and vendor_friendly_probability (0-1).
    """
    signals_found = []

    desc = company_data.get("description", "").lower()
    jds = " ".join(company_data.get("jd_samples", [])).lower()
    combined = desc + " " + jds

    positive_signals = [
        "empanelled vendors", "approved vendor list", "third party ok",
        "staffing welcome", "contract positions", "c2h",
    ]
    negative_signals = [
        "direct applicants only", "no consultants", "no vendors",
        "no third party", "direct hire only",
    ]

    pos_count = sum(1 for s in positive_signals if s in combined)
    neg_count = sum(1 for s in negative_signals if s in combined)

    if neg_count > 0:
        probability = max(0.0, 0.3 - neg_count * 0.1)
        verdict = "NOT_VENDOR_FRIENDLY"
    elif pos_count > 0:
        probability = min(1.0, 0.6 + pos_count * 0.1)
        verdict = "VENDOR_FRIENDLY"
        signals_found = [s for s in positive_signals if s in combined]
    else:
        probability = 0.5
        verdict = "UNKNOWN"

    return {
        "verdict": verdict,
        "vendor_friendly_probability": round(probability, 2),
        "positive_signals_found": signals_found,
        "negative_signals_found": [s for s in negative_signals if s in combined],
        "confidence": "HIGH" if abs(probability - 0.5) > 0.3 else "LOW",
    }


@tool
def assess_budget_range(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate a company's recruitment budget and willingness to pay placement fees.

    Args:
        company_data: Company info including size, funding, and industry.

    Returns:
        Dict with estimated_fee_range, fee_model_preference, and budget_tier.
    """
    size = company_data.get("employee_count", 0)
    company_type = company_data.get("company_type", "IT Services")
    funding_stage = company_data.get("funding_stage", "unknown")

    # Fee range estimation based on company profile
    if size > 10000 or company_type == "GCC":
        fee_range = "₹1.5L – ₹5L per placement"
        fee_model = "percentage_of_ctc"
        tier = "ENTERPRISE"
    elif size > 1000 or funding_stage in ["Series B", "Series C", "IPO"]:
        fee_range = "₹75K – ₹2L per placement"
        fee_model = "percentage_or_flat"
        tier = "MID_MARKET"
    elif funding_stage in ["Series A", "Seed"]:
        fee_range = "₹30K – ₹75K per placement"
        fee_model = "flat_fee"
        tier = "STARTUP"
    else:
        fee_range = "₹25K – ₹50K per placement"
        fee_model = "flat_fee"
        tier = "SMB"

    return {
        "estimated_fee_range": fee_range,
        "fee_model_preference": fee_model,
        "budget_tier": tier,
        "annual_hiring_budget_estimate": {
            "ENTERPRISE": "₹25L+",
            "MID_MARKET": "₹5L – ₹25L",
            "STARTUP": "₹1L – ₹5L",
            "SMB": "< ₹1L",
        }[tier],
    }


@tool
def score_lead_quality(
    company_data: Dict[str, Any],
    hiring_activity: Dict[str, Any],
    vendor_check: Dict[str, Any],
    budget_assessment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute a composite lead quality score (0-100) with breakdown.

    Factors:
        - Hiring frequency (20 pts)
        - Vendor friendliness (20 pts)
        - Responsiveness history (15 pts)
        - Remote flexibility (10 pts)
        - Salary range competitiveness (10 pts)
        - Contract/C2H ops (10 pts)
        - Placement probability (15 pts)

    Returns:
        Dict with total_score, breakdown, tier, and recommended_action.
    """
    breakdown: Dict[str, float] = {}

    # Hiring frequency (20 pts)
    avg_monthly = float(hiring_activity.get("avg_monthly_postings", 0))
    breakdown["hiring_frequency"] = min(20.0, avg_monthly * 2)

    # Vendor friendliness (20 pts)
    vf_prob = float(vendor_check.get("vendor_friendly_probability", 0.5))
    breakdown["vendor_friendliness"] = round(vf_prob * 20, 1)

    # Responsiveness (15 pts) – based on historical data
    response_rate = float(company_data.get("historical_response_rate", 0.3))
    breakdown["responsiveness"] = round(response_rate * 15, 1)

    # Remote flexibility (10 pts)
    remote = company_data.get("remote_policy", "").lower()
    breakdown["remote_flexibility"] = 10.0 if "remote" in remote else 6.0 if "hybrid" in remote else 3.0

    # Salary competitiveness (10 pts)
    budget_tier = budget_assessment.get("budget_tier", "SMB")
    tier_scores = {"ENTERPRISE": 10, "MID_MARKET": 8, "STARTUP": 6, "SMB": 4}
    breakdown["salary_range"] = float(tier_scores.get(budget_tier, 4))

    # Contract/C2H (10 pts)
    c2h = bool(company_data.get("c2h_detected", False))
    contract = bool(company_data.get("accepts_contract", False))
    breakdown["contract_ops"] = 10.0 if (c2h or contract) else 4.0

    # Placement probability (15 pts) – based on company type and size
    company_type = company_data.get("company_type", "IT Services")
    prob_map = {"Product": 15, "GCC": 14, "AIML": 13, "FinTech": 12, "Startup": 11, "IT Services": 8}
    breakdown["placement_probability"] = float(prob_map.get(company_type, 7))

    total = sum(breakdown.values())
    total = min(100.0, round(total, 1))

    tier = "HOT" if total >= 75 else "WARM" if total >= 50 else "COLD"

    return {
        "total_score": total,
        "score_breakdown": breakdown,
        "tier": tier,
        "recommended_action": {
            "HOT": "Immediate personal outreach – assign senior recruiter",
            "WARM": "Schedule automated email sequence + LinkedIn connect",
            "COLD": "Add to monthly newsletter, re-evaluate in 30 days",
        }[tier],
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class LeadQualificationAgent(BaseAgent):
    """
    LangGraph agent for qualifying and prioritizing employer leads.

    Workflow:
        research_lead -> verify_contact -> score_quality ->
        classify_priority -> assign_action -> END
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="LeadQualificationAgent", **kwargs)
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(LeadQualificationState)
        workflow.add_node("research_lead", self._node_research_lead)
        workflow.add_node("verify_contact", self._node_verify_contact)
        workflow.add_node("score_quality", self._node_score_quality)
        workflow.add_node("classify_priority", self._node_classify_priority)
        workflow.add_node("assign_action", self._node_assign_action)

        workflow.set_entry_point("research_lead")
        workflow.add_edge("research_lead", "verify_contact")
        workflow.add_edge("verify_contact", "score_quality")
        workflow.add_edge("score_quality", "classify_priority")
        workflow.add_edge("classify_priority", "assign_action")
        workflow.add_edge("assign_action", END)
        return workflow.compile()

    async def _node_research_lead(self, state: LeadQualificationState) -> LeadQualificationState:
        self.log_state_transition("START", "research_lead", list(state.keys()))
        lead = state.get("lead", {})
        company_name = lead.get("name", "Unknown")
        website = lead.get("website")

        prompt = f"""Research the company "{company_name}" for recruitment purposes.
Website: {website or 'unknown'}

Provide a JSON response with:
{{
  "recent_news": ["news item 1", ...],
  "funding_stage": "Series A/B/C/Public/Private/Unknown",
  "employee_count": <estimated integer>,
  "employee_growth_trend": "growing/stable/shrinking",
  "tech_stack": ["tech1", "tech2"],
  "glassdoor_rating": <float or null>,
  "linkedin_followers": <integer or null>,
  "remote_policy": "remote/hybrid/onsite",
  "accepts_contract": <true/false>,
  "historical_response_rate": <float 0-1>,
  "key_decision_makers": ["name - title", ...]
}}

Respond ONLY with valid JSON."""

        try:
            response = await self.invoke_llm([{"role": "user", "content": prompt}])
            cleaned = response.strip().lstrip("```json").lstrip("```").rstrip("```")
            research_data = json.loads(cleaned)
        except Exception as exc:
            self.logger.warning("Research LLM call failed: %s", exc)
            research_data = research_company.invoke({
                "company_name": company_name,
                "website": website,
            })

        merged_lead = {**lead, **research_data}
        return {**state, "lead": merged_lead, "research_data": research_data}

    async def _node_verify_contact(self, state: LeadQualificationState) -> LeadQualificationState:
        self.log_state_transition("research_lead", "verify_contact", list(state.keys()))
        lead = state.get("lead", {})
        contacts = lead.get("contacts", [])
        verified = bool(contacts) and any(c.get("email") for c in contacts if isinstance(c, dict))
        return {**state, "contact_verified": verified}

    async def _node_score_quality(self, state: LeadQualificationState) -> LeadQualificationState:
        self.log_state_transition("verify_contact", "score_quality", list(state.keys()))
        lead = state.get("lead", {})

        hiring_activity = check_hiring_activity.invoke({
            "company_name": lead.get("name", ""),
            "platform": "naukri.com",
        })
        vendor_check = verify_vendor_friendliness.invoke({"company_data": lead})
        budget = assess_budget_range.invoke({"company_data": lead})

        quality = score_lead_quality.invoke({
            "company_data": lead,
            "hiring_activity": hiring_activity,
            "vendor_check": vendor_check,
            "budget_assessment": budget,
        })

        return {**state, "quality_score": quality}

    async def _node_classify_priority(self, state: LeadQualificationState) -> LeadQualificationState:
        self.log_state_transition("score_quality", "classify_priority", list(state.keys()))
        quality = state.get("quality_score", {})
        tier = quality.get("tier", "COLD")
        return {**state, "priority_class": tier}

    async def _node_assign_action(self, state: LeadQualificationState) -> LeadQualificationState:
        self.log_state_transition("classify_priority", "assign_action", list(state.keys()))
        quality = state.get("quality_score", {})
        lead = state.get("lead", {})
        priority = state.get("priority_class", "COLD")

        action_plan = {
            "priority": priority,
            "recommended_action": quality.get("recommended_action", "Monitor"),
            "next_step": quality.get("recommended_action", "Monitor"),
            "assigned_at": time.time(),
            "estimated_conversion_days": {"HOT": 14, "WARM": 30, "COLD": 90}.get(priority, 90),
        }

        try:
            self.publish_to_kafka(
                topic=KAFKA_TOPIC_EMPLOYER_QUALIFIED,
                payload={
                    "company_id": lead.get("company_id", str(uuid.uuid4())),
                    "company_name": lead.get("name"),
                    "quality_score": quality.get("total_score"),
                    "tier": priority,
                    "action_plan": action_plan,
                },
                key=lead.get("company_id"),
            )
        except Exception as exc:
            self.logger.warning("Kafka publish failed: %s", exc)

        return {**state, "action_plan": action_plan}

    async def run(
        self,
        task: str,
        lead: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Qualify a single employer lead and return scoring + action plan."""
        initial_state: LeadQualificationState = {
            "messages": [],
            "task": task,
            "lead": lead or {},
            "research_data": None,
            "contact_verified": False,
            "quality_score": None,
            "priority_class": None,
            "action_plan": None,
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }
        final = await self._graph.ainvoke(initial_state)
        return {
            "lead": final.get("lead"),
            "quality_score": final.get("quality_score"),
            "priority_class": final.get("priority_class"),
            "action_plan": final.get("action_plan"),
            "contact_verified": final.get("contact_verified"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        result = await self.run(
            task=state.get("task", "qualify lead"),
            lead=state.get("metadata", {}).get("lead"),
        )
        return {**state, "result": result, "updated_at": time.time()}

    async def qualify_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Qualify a list of leads concurrently."""
        import asyncio
        tasks = [self.run(task="qualify lead", lead=lead) for lead in leads]
        return await asyncio.gather(*tasks)
