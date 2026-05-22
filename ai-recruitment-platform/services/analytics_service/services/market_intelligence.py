"""Market intelligence: demand prediction, salary analysis, trend detection."""
import json
import logging
from typing import Any, Dict, List, Optional
from common.llm import generate_text
from common.config import settings

logger = logging.getLogger(__name__)


class MarketIntelligenceService:
    """AI-powered market intelligence for the Indian IT recruitment market."""

    async def predict_role_demand(
        self, role: str, region: str = "India", months_ahead: int = 3
    ) -> Dict[str, Any]:
        """Predict demand trend for a role over coming months."""
        prompt = f"""
Analyze the current and projected demand for '{role}' professionals in {region} over the next {months_ahead} months.
Consider: current job postings trends, technology adoption, economic factors, hiring cycles.
Return JSON with: demand_level (very_high/high/medium/low), trend (increasing/stable/decreasing),
confidence (0-1), key_drivers (list), risk_factors (list), projected_openings_per_month.
"""
        try:
            response = await generate_text(prompt, temperature=0.1)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Demand prediction failed for {role}: {e}")

        return {
            "demand_level": "high",
            "trend": "increasing",
            "confidence": 0.7,
            "key_drivers": ["Digital transformation", "Cloud adoption", "AI/ML growth"],
            "risk_factors": ["Economic slowdown", "Automation"],
            "projected_openings_per_month": 500,
        }

    async def get_salary_benchmarks(
        self, role: str, location: str, yoe_min: int = 0, yoe_max: int = 10
    ) -> Dict[str, Any]:
        """Get salary benchmark data from static data + AI enrichment."""
        try:
            with open("/app/data/salary_benchmarks_india.json") as f:
                static_data = json.load(f)
            role_data = static_data.get("roles", {}).get(role, {})
            for yoe_range, data in role_data.items():
                start = int(yoe_range.split("-")[0]) if "-" in yoe_range else int(yoe_range.replace("+", ""))
                if yoe_min >= start:
                    cities = data.get("cities", {})
                    city_data = cities.get(location, data)
                    return {
                        "role": role, "location": location,
                        "yoe_range": f"{yoe_min}-{yoe_max}",
                        "min": city_data.get("min", data.get("min", 0)),
                        "median": city_data.get("median", data.get("median", 0)),
                        "max": city_data.get("max", data.get("max", 0)),
                        "currency": "INR",
                        "source": "market_data",
                    }
        except Exception as e:
            logger.warning(f"Salary benchmark lookup failed: {e}")
        return {"role": role, "location": location, "min": 0, "median": 0, "max": 0, "currency": "INR"}

    async def analyze_hiring_trends(
        self, industry: str, region: str = "India"
    ) -> Dict[str, Any]:
        """Analyze hiring trends in an industry segment."""
        prompt = f"""
Analyze current hiring trends in the {industry} sector in {region}.
Focus on: hot roles, declining roles, salary movements, remote vs onsite shifts,
top companies expanding headcount, emerging skill requirements.
Be specific and actionable for a recruitment agency.
"""
        try:
            analysis = await generate_text(prompt, temperature=0.2)
            return {"industry": industry, "region": region, "analysis": analysis}
        except Exception as e:
            return {"industry": industry, "region": region, "analysis": f"Analysis unavailable: {e}"}

    async def identify_emerging_skills(self, role: str) -> List[str]:
        """Identify up-and-coming skills for a role."""
        emerging_skills_map = {
            "Java Developer": ["Virtual Threads (Java 21)", "GraalVM", "Quarkus", "Micronaut"],
            "AI Engineer": ["LangChain", "LangGraph", "RAG", "Vector Databases", "Fine-tuning LLMs"],
            "Cloud Engineer": ["FinOps", "Platform Engineering", "Internal Developer Platform"],
            "DevOps Engineer": ["Platform Engineering", "GitOps", "Backstage", "Crossplane"],
            "Data Engineer": ["Apache Iceberg", "Databricks", "dbt", "Streaming Analytics"],
        }
        return emerging_skills_map.get(role, ["Python", "Cloud", "AI/ML", "Kubernetes"])

    async def predict_placement_probability(
        self, candidate: Dict[str, Any], job: Dict[str, Any]
    ) -> float:
        """Predict probability of successful placement (0-1)."""
        skill_match = len(set(candidate.get("skills", [])) & set(job.get("skills_required", [])))
        total_required = len(job.get("skills_required", []))
        skill_score = skill_match / total_required if total_required > 0 else 0.5

        exp_required = job.get("min_experience", 0) or 0
        exp_candidate = candidate.get("years_experience", 0) or 0
        exp_score = min(1.0, exp_candidate / max(exp_required, 1))

        probability = (skill_score * 0.6 + exp_score * 0.4)
        return round(min(0.95, probability), 2)
