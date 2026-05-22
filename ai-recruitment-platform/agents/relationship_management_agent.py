"""
Relationship Management Agent
LangGraph-based agent for tracking, scoring, and nurturing recruiter/hiring-manager
relationships over time.
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


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class RelationshipState(TypedDict, total=False):
    """State for the RelationshipManagementAgent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    contact: Dict[str, Any]
    interaction_history: List[Dict[str, Any]]
    relationship_score: Optional[Dict[str, Any]]
    next_action: Optional[Dict[str, Any]]
    touchpoint_content: Optional[str]
    conversion_prediction: Optional[Dict[str, Any]]
    updated_contact: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def update_contact_history(
    contact_id: str,
    interaction: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add a new interaction to a contact's history.

    Args:
        contact_id: Unique identifier for the contact.
        interaction: Dict with type, channel, content, outcome, timestamp.

    Returns:
        Updated contact record with interaction appended.
    """
    return {
        "contact_id": contact_id,
        "interaction_recorded": True,
        "interaction": {
            **interaction,
            "recorded_at": time.time(),
            "interaction_id": str(uuid.uuid4()),
        },
    }


@tool
def calculate_relationship_score(
    contact: Dict[str, Any],
    interaction_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calculate a comprehensive relationship health score (0-100).

    Factors:
        - Interaction frequency (25 pts)
        - Response rate (25 pts)
        - Placement history (25 pts)
        - Deal value generated (25 pts)

    Args:
        contact: Contact data including placement_count and deal_value.
        interaction_history: List of past interactions.

    Returns:
        Dict with total_score, breakdown, health_label, and trend.
    """
    breakdown: Dict[str, float] = {}
    now = time.time()

    # Interaction frequency (25 pts) – how many interactions in last 90 days
    recent_cutoff = now - 90 * 86400
    recent = [i for i in interaction_history if i.get("timestamp", 0) > recent_cutoff]
    freq_score = min(25.0, len(recent) * 3.0)
    breakdown["interaction_frequency"] = round(freq_score, 1)

    # Response rate (25 pts)
    total_outreach = sum(1 for i in interaction_history if i.get("type") == "outreach")
    responses = sum(1 for i in interaction_history if i.get("type") == "response" and i.get("is_positive"))
    if total_outreach > 0:
        rate = responses / total_outreach
        breakdown["response_rate"] = round(rate * 25, 1)
    else:
        breakdown["response_rate"] = 5.0  # neutral starting score

    # Placement history (25 pts)
    placement_count = int(contact.get("placement_count", 0))
    breakdown["placement_history"] = min(25.0, placement_count * 5.0)

    # Deal value (25 pts)
    deal_value = float(contact.get("total_deal_value", 0))
    deal_score = min(25.0, deal_value / 100000 * 25)  # normalised to ₹1L = 25 pts
    breakdown["deal_value"] = round(deal_score, 1)

    total = sum(breakdown.values())
    total = min(100.0, round(total, 1))

    # Historical trend
    old_score = float(contact.get("previous_relationship_score", total))
    trend = "improving" if total > old_score + 5 else "declining" if total < old_score - 5 else "stable"

    return {
        "total_score": total,
        "score_breakdown": breakdown,
        "health_label": "Excellent" if total >= 80 else "Good" if total >= 60 else "Fair" if total >= 40 else "At Risk",
        "trend": trend,
        "last_calculated": now,
    }


@tool
def identify_next_action(
    contact: Dict[str, Any],
    relationship_score: Dict[str, Any],
    last_interaction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Recommend the most impactful next action to strengthen the relationship.

    Args:
        contact: Contact data.
        relationship_score: Output from calculate_relationship_score.
        last_interaction: Most recent interaction record.

    Returns:
        Dict with action_type, channel, priority, and suggested_content_hint.
    """
    score = relationship_score.get("total_score", 50)
    health = relationship_score.get("health_label", "Fair")
    days_since_last = 999

    if last_interaction:
        last_ts = last_interaction.get("timestamp", 0)
        days_since_last = (time.time() - last_ts) / 86400

    if health == "Excellent" and days_since_last < 30:
        action = {
            "action_type": "value_add_share",
            "channel": "email",
            "priority": "LOW",
            "suggested_content_hint": "Share industry salary report or market insights",
        }
    elif health in ("Good", "Excellent") and days_since_last > 30:
        action = {
            "action_type": "check_in",
            "channel": "linkedin",
            "priority": "MEDIUM",
            "suggested_content_hint": "Casual check-in, ask about current hiring pipeline",
        }
    elif health == "Fair":
        action = {
            "action_type": "re_engagement",
            "channel": "email",
            "priority": "HIGH",
            "suggested_content_hint": "Send fresh candidate profiles matching their recent job postings",
        }
    else:  # At Risk
        action = {
            "action_type": "win_back",
            "channel": "phone",
            "priority": "URGENT",
            "suggested_content_hint": "Personal call to understand pain points, offer exclusive deal",
        }

    action["contact_name"] = contact.get("name", "")
    action["scheduled_for"] = time.time() + {"URGENT": 0, "HIGH": 86400, "MEDIUM": 3 * 86400, "LOW": 7 * 86400}.get(action["priority"], 86400)
    return action


@tool
def generate_touchpoint(
    contact: Dict[str, Any],
    action_type: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate personalised touchpoint content (message / talking points).

    Args:
        contact: Contact information.
        action_type: Type of action (check_in/value_add_share/re_engagement/win_back).
        context: Additional context for content generation.

    Returns:
        Formatted touchpoint message string.
    """
    ctx = context or {}
    name = contact.get("first_name", contact.get("name", "there"))
    company = contact.get("company_name", "your company")

    content_map = {
        "check_in": (
            f"Hi {name},\n\nHope you're doing well! Quick check-in from my side — "
            f"any new tech hiring needs at {company} I should know about? "
            f"We've been placing great talent lately and would love to help.\n\nBest,"
        ),
        "value_add_share": (
            f"Hi {name},\n\nI came across this {ctx.get('resource_type', 'market report')} "
            f"on {ctx.get('topic', 'tech hiring trends')} and thought of you. "
            f"Thought it might be useful for your planning at {company}. Happy to chat about it!\n\nBest,"
        ),
        "re_engagement": (
            f"Hi {name},\n\nI've been reviewing our earlier conversations and realised I haven't "
            f"followed up in a while. We have some excellent {ctx.get('role_type', 'tech')} candidates "
            f"with your tech stack who are actively looking. Would you like me to share profiles?\n\nBest,"
        ),
        "win_back": (
            f"Hi {name},\n\nI wanted to personally reach out — I'd value your feedback on how we can serve "
            f"{company} better. As a gesture of appreciation, I'd like to offer a complimentary profile review "
            f"for your next open role. Can we get 10 minutes on a call?\n\nWith respect,"
        ),
    }

    return content_map.get(action_type, content_map["check_in"])


@tool
def predict_conversion(
    contact: Dict[str, Any],
    relationship_score: Dict[str, Any],
    market_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Predict the probability of a successful placement conversion in the next 90 days.

    Args:
        contact: Contact and company data.
        relationship_score: Current relationship health score.
        market_context: Optional market conditions (hiring season, demand trends).

    Returns:
        Dict with conversion_probability (0-1), confidence, and key_drivers.
    """
    score = relationship_score.get("total_score", 50) / 100
    placement_history = min(1.0, contact.get("placement_count", 0) / 5)
    response_rate = contact.get("response_rate", 0.3)
    company_hiring_trend = contact.get("hiring_trend", "stable")
    market_demand = float((market_context or {}).get("demand_score", 0.6))

    # Weighted probability
    probability = (
        score * 0.35
        + placement_history * 0.25
        + response_rate * 0.20
        + (1.0 if company_hiring_trend == "growing" else 0.5 if company_hiring_trend == "stable" else 0.2) * 0.10
        + market_demand * 0.10
    )
    probability = round(min(1.0, probability), 3)

    return {
        "conversion_probability": probability,
        "probability_label": "HIGH" if probability >= 0.65 else "MEDIUM" if probability >= 0.35 else "LOW",
        "confidence": "moderate",
        "key_drivers": {
            "relationship_health": f"{relationship_score.get('health_label')} ({score:.0%})",
            "placement_track_record": f"{contact.get('placement_count', 0)} placements",
            "response_rate": f"{response_rate:.0%}",
            "hiring_trend": company_hiring_trend,
        },
        "predicted_placements_90_days": round(probability * 2.5, 1),
        "estimated_revenue_inr": round(probability * 2.5 * 75000, 0),
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class RelationshipManagementAgent(BaseAgent):
    """
    LangGraph agent for managing recruiter and hiring-manager relationships.

    Workflow:
        update_history -> calculate_score -> identify_action ->
        generate_touchpoint -> predict_conversion -> END
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="RelationshipManagementAgent", **kwargs)
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(RelationshipState)
        workflow.add_node("update_history", self._node_update_history)
        workflow.add_node("calculate_score", self._node_calculate_score)
        workflow.add_node("identify_action", self._node_identify_action)
        workflow.add_node("generate_touchpoint_node", self._node_generate_touchpoint)
        workflow.add_node("predict_conversion_node", self._node_predict_conversion)

        workflow.set_entry_point("update_history")
        workflow.add_edge("update_history", "calculate_score")
        workflow.add_edge("calculate_score", "identify_action")
        workflow.add_edge("identify_action", "generate_touchpoint_node")
        workflow.add_edge("generate_touchpoint_node", "predict_conversion_node")
        workflow.add_edge("predict_conversion_node", END)
        return workflow.compile()

    async def _node_update_history(self, state: RelationshipState) -> RelationshipState:
        self.log_state_transition("START", "update_history", list(state.keys()))
        contact = state.get("contact", {})
        new_interaction = state.get("task", "")

        if new_interaction and isinstance(new_interaction, str):
            update_contact_history.invoke({
                "contact_id": contact.get("id", str(uuid.uuid4())),
                "interaction": {
                    "type": "note",
                    "content": new_interaction,
                    "timestamp": time.time(),
                    "channel": "system",
                },
            })
        return state

    async def _node_calculate_score(self, state: RelationshipState) -> RelationshipState:
        self.log_state_transition("update_history", "calculate_score", list(state.keys()))
        contact = state.get("contact", {})
        history = state.get("interaction_history", [])
        score = calculate_relationship_score.invoke({
            "contact": contact,
            "interaction_history": history,
        })
        return {**state, "relationship_score": score}

    async def _node_identify_action(self, state: RelationshipState) -> RelationshipState:
        self.log_state_transition("calculate_score", "identify_action", list(state.keys()))
        contact = state.get("contact", {})
        score = state.get("relationship_score", {})
        history = state.get("interaction_history", [])
        last = history[-1] if history else None

        action = identify_next_action.invoke({
            "contact": contact,
            "relationship_score": score,
            "last_interaction": last,
        })

        # Enrich with LLM insight
        try:
            prompt = (
                f"Given a recruitment contact with relationship score {score.get('total_score')}/100 "
                f"({score.get('health_label')}), {len(history)} past interactions, "
                f"and {contact.get('placement_count', 0)} placements, suggest ONE specific and creative "
                f"outreach action in 1-2 sentences. Be concise and actionable."
            )
            enrichment = await self.invoke_llm([{"role": "user", "content": prompt}])
            action["llm_suggestion"] = enrichment.strip()
        except Exception:
            pass

        return {**state, "next_action": action}

    async def _node_generate_touchpoint(self, state: RelationshipState) -> RelationshipState:
        self.log_state_transition("identify_action", "generate_touchpoint_node", list(state.keys()))
        contact = state.get("contact", {})
        action = state.get("next_action", {})
        action_type = action.get("action_type", "check_in")

        content = generate_touchpoint.invoke({
            "contact": contact,
            "action_type": action_type,
        })

        # Use LLM to make it more personal
        try:
            prompt = (
                f"Rewrite the following relationship touchpoint message to sound more personal and genuine. "
                f"Contact: {contact.get('name', '')} at {contact.get('company_name', '')}. "
                f"Keep it under 100 words.\n\n---\n{content}\n---\n\n"
                f"Return ONLY the improved message."
            )
            improved = await self.invoke_llm([{"role": "user", "content": prompt}])
            content = improved.strip()
        except Exception:
            pass

        return {**state, "touchpoint_content": content}

    async def _node_predict_conversion(self, state: RelationshipState) -> RelationshipState:
        self.log_state_transition("generate_touchpoint_node", "predict_conversion_node", list(state.keys()))
        prediction = predict_conversion.invoke({
            "contact": state.get("contact", {}),
            "relationship_score": state.get("relationship_score", {}),
        })
        updated_contact = {
            **state.get("contact", {}),
            "relationship_score": state.get("relationship_score", {}).get("total_score"),
            "conversion_probability": prediction.get("conversion_probability"),
            "last_assessed": time.time(),
        }
        return {**state, "conversion_prediction": prediction, "updated_contact": updated_contact}

    async def run(
        self,
        task: str,
        contact: Optional[Dict[str, Any]] = None,
        interaction_history: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Assess and manage a contact relationship."""
        initial: RelationshipState = {
            "messages": [],
            "task": task,
            "contact": contact or {},
            "interaction_history": interaction_history or [],
            "relationship_score": None,
            "next_action": None,
            "touchpoint_content": None,
            "conversion_prediction": None,
            "updated_contact": None,
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }
        final = await self._graph.ainvoke(initial)
        return {
            "relationship_score": final.get("relationship_score"),
            "next_action": final.get("next_action"),
            "touchpoint_content": final.get("touchpoint_content"),
            "conversion_prediction": final.get("conversion_prediction"),
            "updated_contact": final.get("updated_contact"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "manage relationship"),
            contact=meta.get("contact"),
            interaction_history=meta.get("interaction_history"),
        )
        return {**state, "result": result, "updated_at": time.time()}
