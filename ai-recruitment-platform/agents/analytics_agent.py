"""
Analytics Agent
LangGraph-based agent for computing platform analytics, generating reports,
predicting placement probabilities, and providing market intelligence.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta
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

class AnalyticsState(TypedDict, total=False):
    """State for the AnalyticsAgent LangGraph workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    report_type: str
    date_range: Dict[str, str]
    raw_metrics: Optional[Dict[str, Any]]
    conversion_rates: Optional[Dict[str, Any]]
    outreach_performance: Optional[Dict[str, Any]]
    placement_predictions: Optional[Dict[str, Any]]
    market_intelligence: Optional[Dict[str, Any]]
    weekly_report: Optional[str]
    top_templates: Optional[List[Dict[str, Any]]]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def compute_conversion_rates(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute funnel conversion rates from raw platform metrics.

    Args:
        metrics: Dict with counts at each funnel stage.

    Returns:
        Dict with conversion rates at each stage and overall funnel efficiency.
    """
    employers_discovered = max(1, metrics.get("employers_discovered", 1))
    employers_qualified = metrics.get("employers_qualified", 0)
    outreach_sent = metrics.get("outreach_sent", 0)
    emails_opened = metrics.get("emails_opened", 0)
    responses_received = metrics.get("responses_received", 0)
    meetings_scheduled = metrics.get("meetings_scheduled", 0)
    candidates_submitted = metrics.get("candidates_submitted", 0)
    placements_made = metrics.get("placements_made", 0)

    def rate(numerator: int, denominator: int) -> float:
        return round(numerator / max(1, denominator) * 100, 2)

    return {
        "discovery_to_qualification": rate(employers_qualified, employers_discovered),
        "qualification_to_outreach": rate(outreach_sent, employers_qualified),
        "outreach_to_open": rate(emails_opened, outreach_sent),
        "open_to_response": rate(responses_received, emails_opened),
        "response_to_meeting": rate(meetings_scheduled, responses_received),
        "meeting_to_submission": rate(candidates_submitted, meetings_scheduled),
        "submission_to_placement": rate(placements_made, candidates_submitted),
        "overall_discovery_to_placement": rate(placements_made, employers_discovered),
        "funnel_summary": {
            "employers_discovered": employers_discovered,
            "employers_qualified": employers_qualified,
            "outreach_sent": outreach_sent,
            "emails_opened": emails_opened,
            "responses": responses_received,
            "meetings": meetings_scheduled,
            "submissions": candidates_submitted,
            "placements": placements_made,
        },
    }


@tool
def analyze_outreach_performance(
    outreach_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyse outreach campaign performance by channel, template, and segment.

    Args:
        outreach_data: List of outreach records with channel, template_type, opened, replied fields.

    Returns:
        Dict with per-channel stats, per-template stats, best_performing_segment.
    """
    channel_stats: Dict[str, Dict[str, int]] = {}
    template_stats: Dict[str, Dict[str, int]] = {}

    for record in outreach_data:
        channel = record.get("channel", "email")
        template = record.get("template_type", "unknown")

        for stats, key in [(channel_stats, channel), (template_stats, template)]:
            if key not in stats:
                stats[key] = {"sent": 0, "opened": 0, "replied": 0, "positive": 0}
            stats[key]["sent"] += 1
            if record.get("opened"):
                stats[key]["opened"] += 1
            if record.get("replied"):
                stats[key]["replied"] += 1
            if record.get("is_positive_response"):
                stats[key]["positive"] += 1

    def enrich(stats: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        return {
            k: {
                **v,
                "open_rate": round(v["opened"] / max(1, v["sent"]) * 100, 1),
                "reply_rate": round(v["replied"] / max(1, v["sent"]) * 100, 1),
                "positive_rate": round(v["positive"] / max(1, v["sent"]) * 100, 1),
            }
            for k, v in stats.items()
        }

    enriched_channel = enrich(channel_stats)
    enriched_template = enrich(template_stats)

    best_channel = max(enriched_channel.items(), key=lambda x: x[1].get("reply_rate", 0), default=("email", {}))[0] if enriched_channel else "email"
    best_template = max(enriched_template.items(), key=lambda x: x[1].get("positive_rate", 0), default=("cold_outreach", {}))[0] if enriched_template else "cold_outreach"

    return {
        "by_channel": enriched_channel,
        "by_template": enriched_template,
        "best_performing_channel": best_channel,
        "best_performing_template": best_template,
        "total_outreach_analyzed": len(outreach_data),
    }


@tool
def predict_placement_probability(
    pipeline_data: Dict[str, Any],
    historical_rates: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Predict expected placements and revenue for the next 30/60/90 days.

    Args:
        pipeline_data: Current pipeline counts at each stage.
        historical_rates: Historical conversion rates from compute_conversion_rates.

    Returns:
        Dict with predictions at 30/60/90 day horizons and confidence intervals.
    """
    meetings_in_pipeline = pipeline_data.get("active_meetings", 0)
    submissions_in_pipeline = pipeline_data.get("active_submissions", 0)
    avg_placement_fee_inr = pipeline_data.get("avg_placement_fee", 75000)

    meeting_to_placement_rate = historical_rates.get("meeting_to_submission", 40) / 100 * \
                                 historical_rates.get("submission_to_placement", 50) / 100

    predicted_from_meetings = meetings_in_pipeline * meeting_to_placement_rate
    predicted_from_submissions = submissions_in_pipeline * (historical_rates.get("submission_to_placement", 50) / 100)

    total_30d = round(predicted_from_submissions * 0.7, 1)
    total_60d = round((predicted_from_submissions + predicted_from_meetings * 0.5), 1)
    total_90d = round(predicted_from_meetings + predicted_from_submissions, 1)

    return {
        "predicted_placements": {
            "30_days": total_30d,
            "60_days": total_60d,
            "90_days": total_90d,
        },
        "predicted_revenue_inr": {
            "30_days": round(total_30d * avg_placement_fee_inr),
            "60_days": round(total_60d * avg_placement_fee_inr),
            "90_days": round(total_90d * avg_placement_fee_inr),
        },
        "confidence": "moderate",
        "assumptions": {
            "meeting_to_placement_rate": f"{meeting_to_placement_rate:.1%}",
            "avg_placement_fee": f"₹{avg_placement_fee_inr:,.0f}",
        },
    }


@tool
def identify_top_templates(
    outreach_analysis: Dict[str, Any],
    min_sample_size: int = 10,
) -> List[Dict[str, Any]]:
    """
    Identify the highest-performing email/message templates.

    Args:
        outreach_analysis: Output from analyze_outreach_performance.
        min_sample_size: Minimum sends required to qualify.

    Returns:
        List of top templates sorted by positive response rate.
    """
    by_template = outreach_analysis.get("by_template", {})
    qualified = [
        {"template": k, **v}
        for k, v in by_template.items()
        if v.get("sent", 0) >= min_sample_size
    ]
    qualified.sort(key=lambda t: t.get("positive_rate", 0), reverse=True)
    return qualified[:5]


@tool
def predict_market_demand(role: str, region: str = "India") -> Dict[str, Any]:
    """
    Predict demand trends for a specific tech role in a region.

    Args:
        role: Job role to analyse.
        region: Geographic region.

    Returns:
        Dict with demand_score (0-10), trend, top_hiring_companies, salary_range.
    """
    # In production: analyses job posting volume trends from scraped data
    demand_map = {
        "AI Engineer": {"demand_score": 9.5, "trend": "rapidly_growing", "yoy_growth": "180%"},
        "Cloud Engineer": {"demand_score": 8.5, "trend": "growing", "yoy_growth": "45%"},
        "DevOps Engineer": {"demand_score": 8.0, "trend": "growing", "yoy_growth": "35%"},
        "Data Engineer": {"demand_score": 8.2, "trend": "growing", "yoy_growth": "55%"},
        "Java Developer": {"demand_score": 7.5, "trend": "stable", "yoy_growth": "15%"},
        "Full Stack Developer": {"demand_score": 7.8, "trend": "stable", "yoy_growth": "20%"},
        "Cybersecurity Engineer": {"demand_score": 8.8, "trend": "growing", "yoy_growth": "65%"},
        "SAP Consultant": {"demand_score": 6.5, "trend": "stable", "yoy_growth": "8%"},
        "Salesforce Developer": {"demand_score": 7.0, "trend": "growing", "yoy_growth": "25%"},
        "QA Automation Engineer": {"demand_score": 7.2, "trend": "stable", "yoy_growth": "18%"},
    }
    data = demand_map.get(role, {"demand_score": 7.0, "trend": "stable", "yoy_growth": "15%"})

    salary_ranges = {
        "India": {"AI Engineer": "₹18L–₹50L", "Java Developer": "₹8L–₹25L", "Cloud Engineer": "₹12L–₹35L"},
        "USA": {"AI Engineer": "$150K–$250K", "Java Developer": "$90K–$150K", "Cloud Engineer": "$120K–$200K"},
    }
    salary = salary_ranges.get(region, salary_ranges["India"]).get(role, "Varies")

    return {
        "role": role,
        "region": region,
        **data,
        "salary_range": salary,
        "top_hiring_industries": ["Product", "GCC", "AIML", "FinTech"],
        "analysis_date": datetime.utcnow().isoformat(),
    }


@tool
def analyze_recruiter_sentiment(
    response_classifications: List[str],
) -> Dict[str, Any]:
    """
    Analyse recruiter/hiring-manager sentiment from response classifications.

    Args:
        response_classifications: List of classification labels.

    Returns:
        Dict with sentiment_breakdown, overall_sentiment, and market_temperature.
    """
    total = len(response_classifications)
    if total == 0:
        return {"overall_sentiment": "neutral", "confidence": "low", "total_responses": 0}

    positive = sum(1 for c in response_classifications if c in ["interested", "request_more_info"])
    negative = sum(1 for c in response_classifications if c in ["not_interested", "unsubscribe"])
    neutral = total - positive - negative

    pos_rate = positive / total
    neg_rate = negative / total

    if pos_rate >= 0.4:
        sentiment = "very_positive"
        temperature = "hot_market"
    elif pos_rate >= 0.2:
        sentiment = "positive"
        temperature = "warm_market"
    elif neg_rate >= 0.4:
        sentiment = "negative"
        temperature = "cold_market"
    else:
        sentiment = "neutral"
        temperature = "stable_market"

    return {
        "overall_sentiment": sentiment,
        "market_temperature": temperature,
        "sentiment_breakdown": {
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
        },
        "positive_rate": round(pos_rate * 100, 1),
        "confidence": "high" if total >= 50 else "moderate" if total >= 20 else "low",
        "total_responses": total,
    }


@tool
def generate_weekly_report(
    metrics: Dict[str, Any],
    conversion_rates: Dict[str, Any],
    predictions: Dict[str, Any],
    market_intel: Dict[str, Any],
) -> str:
    """
    Generate a formatted weekly performance report.

    Args:
        metrics: Raw platform metrics.
        conversion_rates: Computed conversion rates.
        predictions: Placement predictions.
        market_intel: Market demand intelligence.

    Returns:
        Markdown-formatted weekly report string.
    """
    week_start = (datetime.utcnow() - timedelta(days=7)).strftime("%b %d")
    week_end = datetime.utcnow().strftime("%b %d, %Y")

    placements = metrics.get("placements_made", 0)
    revenue = placements * metrics.get("avg_placement_fee", 75000)

    report = f"""# AI Recruitment Platform – Weekly Report
**Period:** {week_start} – {week_end}

## Executive Summary
- **Placements Made:** {placements}
- **Revenue Generated:** ₹{revenue:,.0f}
- **Employers Discovered:** {metrics.get("employers_discovered", 0)}
- **Outreach Sent:** {metrics.get("outreach_sent", 0)}
- **Responses Received:** {metrics.get("responses_received", 0)}

## Funnel Performance
| Stage | Conversion Rate |
|-------|----------------|
| Discovery → Qualification | {conversion_rates.get("discovery_to_qualification", 0)}% |
| Outreach → Open | {conversion_rates.get("outreach_to_open", 0)}% |
| Open → Response | {conversion_rates.get("open_to_response", 0)}% |
| Meeting → Placement | {conversion_rates.get("meeting_to_submission", 0)}% × {conversion_rates.get("submission_to_placement", 0)}% |

## Revenue Forecast
- **30-Day Prediction:** ₹{predictions.get("predicted_revenue_inr", {}).get("30_days", 0):,.0f}
- **60-Day Prediction:** ₹{predictions.get("predicted_revenue_inr", {}).get("60_days", 0):,.0f}
- **90-Day Prediction:** ₹{predictions.get("predicted_revenue_inr", {}).get("90_days", 0):,.0f}

## Market Intelligence
- **Hottest Role:** {market_intel.get("hottest_role", "AI Engineer")}
- **Market Temperature:** {market_intel.get("market_temperature", "warm_market").replace("_", " ").title()}

---
*Report generated automatically by AI Recruitment Platform Analytics Agent*
*Generated at: {datetime.utcnow().isoformat()}*"""

    return report


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AnalyticsAgent(BaseAgent):
    """
    LangGraph agent for platform analytics and reporting.

    Workflow:
        collect_metrics -> compute_rates -> analyze_outreach ->
        predict_placements -> generate_report -> END
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="AnalyticsAgent", **kwargs)
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(AnalyticsState)
        workflow.add_node("collect_metrics", self._node_collect_metrics)
        workflow.add_node("compute_rates", self._node_compute_rates)
        workflow.add_node("analyze_outreach", self._node_analyze_outreach)
        workflow.add_node("predict_placements", self._node_predict_placements)
        workflow.add_node("generate_report", self._node_generate_report)

        workflow.set_entry_point("collect_metrics")
        workflow.add_edge("collect_metrics", "compute_rates")
        workflow.add_edge("compute_rates", "analyze_outreach")
        workflow.add_edge("analyze_outreach", "predict_placements")
        workflow.add_edge("predict_placements", "generate_report")
        workflow.add_edge("generate_report", END)
        return workflow.compile()

    async def _node_collect_metrics(self, state: AnalyticsState) -> AnalyticsState:
        self.log_state_transition("START", "collect_metrics", list(state.keys()))
        # In production: queries PostgreSQL, MongoDB, Redis for real metrics
        raw_metrics = {
            "employers_discovered": 150,
            "employers_qualified": 45,
            "outreach_sent": 320,
            "emails_opened": 96,
            "responses_received": 28,
            "meetings_scheduled": 12,
            "candidates_submitted": 18,
            "placements_made": 4,
            "avg_placement_fee": 85000,
            "active_meetings": 8,
            "active_submissions": 14,
        }
        cached = await self.cache_get("weekly_metrics")
        if cached:
            raw_metrics = cached
        return {**state, "raw_metrics": raw_metrics}

    async def _node_compute_rates(self, state: AnalyticsState) -> AnalyticsState:
        self.log_state_transition("collect_metrics", "compute_rates", list(state.keys()))
        rates = compute_conversion_rates.invoke({"metrics": state.get("raw_metrics", {})})
        return {**state, "conversion_rates": rates}

    async def _node_analyze_outreach(self, state: AnalyticsState) -> AnalyticsState:
        self.log_state_transition("compute_rates", "analyze_outreach", list(state.keys()))
        # In production: loads real outreach records from database
        sample_data: List[Dict[str, Any]] = []
        performance = analyze_outreach_performance.invoke({"outreach_data": sample_data})
        top_temps = identify_top_templates.invoke({
            "outreach_analysis": performance,
            "min_sample_size": 1,
        })
        return {**state, "outreach_performance": performance, "top_templates": top_temps}

    async def _node_predict_placements(self, state: AnalyticsState) -> AnalyticsState:
        self.log_state_transition("analyze_outreach", "predict_placements", list(state.keys()))
        metrics = state.get("raw_metrics", {})
        rates = state.get("conversion_rates", {})
        predictions = predict_placement_probability.invoke({
            "pipeline_data": metrics,
            "historical_rates": rates,
        })

        # Enrich with LLM market analysis
        try:
            prompt = (
                f"Based on current recruitment market conditions in India for tech roles, "
                f"provide 3 bullet-point insights on hiring trends for Q1 2026. "
                f"Be specific and data-driven. Keep each bullet under 30 words."
            )
            market_commentary = await self.invoke_llm([{"role": "user", "content": prompt}])
        except Exception:
            market_commentary = "Market analysis unavailable."

        hottest_role_data = predict_market_demand.invoke({"role": "AI Engineer", "region": "India"})

        market_intel = {
            "hottest_role": "AI Engineer",
            "market_temperature": "warm_market",
            "llm_insights": market_commentary,
            "ai_engineer_demand": hottest_role_data,
        }
        return {**state, "placement_predictions": predictions, "market_intelligence": market_intel}

    async def _node_generate_report(self, state: AnalyticsState) -> AnalyticsState:
        self.log_state_transition("predict_placements", "generate_report", list(state.keys()))
        report = generate_weekly_report.invoke({
            "metrics": state.get("raw_metrics", {}),
            "conversion_rates": state.get("conversion_rates", {}),
            "predictions": state.get("placement_predictions", {}),
            "market_intel": state.get("market_intelligence", {}),
        })

        # Cache the report for 24 hours
        try:
            await self.cache_set("latest_weekly_report", {"report": report, "generated_at": time.time()}, ttl_seconds=86400)
        except Exception:
            pass

        return {**state, "weekly_report": report}

    async def run(
        self,
        task: str,
        report_type: str = "weekly",
        date_range: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate analytics report and predictions."""
        initial: AnalyticsState = {
            "messages": [],
            "task": task,
            "report_type": report_type,
            "date_range": date_range or {},
            "raw_metrics": None,
            "conversion_rates": None,
            "outreach_performance": None,
            "placement_predictions": None,
            "market_intelligence": None,
            "weekly_report": None,
            "top_templates": None,
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }
        final = await self._graph.ainvoke(initial)
        return {
            "weekly_report": final.get("weekly_report"),
            "conversion_rates": final.get("conversion_rates"),
            "outreach_performance": final.get("outreach_performance"),
            "placement_predictions": final.get("placement_predictions"),
            "market_intelligence": final.get("market_intelligence"),
            "top_templates": final.get("top_templates"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "generate analytics"),
            report_type=meta.get("report_type", "weekly"),
        )
        return {**state, "result": result, "updated_at": time.time()}
