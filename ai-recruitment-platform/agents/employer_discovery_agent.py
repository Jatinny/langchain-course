"""
Employer Discovery Agent
LangGraph-based agent that discovers, classifies, and scores employers across Indian and
global job markets for the AI Recruitment Platform.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Annotated, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base_agent import AgentState, BaseAgent

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class EmployerDiscoveryState(TypedDict, total=False):
    """State for the EmployerDiscoveryAgent LangGraph workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    region: str
    industry: Optional[str]
    target_role: Optional[str]
    raw_companies: List[Dict[str, Any]]
    classified_companies: List[Dict[str, Any]]
    contacts_extracted: List[Dict[str, Any]]
    scored_employers: List[Dict[str, Any]]
    published_count: int
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_ROLES = [
    "Java Developer", "Spring Boot Developer", "AI Engineer",
    "Cloud Engineer", "DevOps Engineer", "Data Engineer",
    "Full Stack Developer", "QA Automation Engineer",
    "SAP Consultant", "Salesforce Developer",
    "Cybersecurity Engineer",
]

REGIONS = ["India", "USA", "Canada", "UK", "Europe", "Singapore", "Australia", "UAE"]

INDIAN_JOB_BOARDS = [
    "naukri.com", "foundit.in", "shine.com", "hirist.tech",
    "timesjobs.com", "apna.co", "cutshort.io", "linkedin.com/jobs",
]

COMPANY_TYPES = [
    "IT Services", "BFSI", "Product", "GCC", "Startup",
    "HealthIT", "EdTech", "FinTech", "Ecomm", "Telecom", "AIML",
]

KAFKA_TOPIC_EMPLOYER_DISCOVERED = "employer.discovered"
KAFKA_TOPIC_EMPLOYER_QUALIFIED = "employer.qualified"

# Signals in job descriptions that suggest vendor/C2H-friendly companies
VENDOR_FRIENDLY_SIGNALS = [
    "contract to hire", "c2h", "contract-to-hire", "corp to corp", "c2c",
    "third party", "vendor empanelment", "staffing partner",
    "w2 only", "bench resources", "contract position",
    "6 months extendable", "immediate joiners",
]

GCC_SIGNALS = [
    "global capability centre", "gcc", "global delivery center",
    "captive center", "offshore development center", "odc",
    "shared services center", "center of excellence",
]


# ---------------------------------------------------------------------------
# LangChain Tools
# ---------------------------------------------------------------------------

@tool
def search_indian_job_boards(
    role: str,
    region: str = "India",
    platform: str = "naukri.com",
) -> Dict[str, Any]:
    """
    Search Indian and global job boards for active hiring companies.

    Args:
        role: Job role to search for (e.g. 'Java Developer').
        region: Geographic region (e.g. 'India', 'USA').
        platform: Job board platform to search.

    Returns:
        Dictionary with 'companies' list and 'total_found' count.
    """
    # In production this delegates to the scraper service.
    return {
        "platform": platform,
        "role": role,
        "region": region,
        "companies": [],
        "total_found": 0,
        "scraped_at": time.time(),
    }


@tool
def detect_vendor_friendly_companies(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse company data and job descriptions to detect vendor-friendly signals.

    Args:
        company_data: Dictionary with company name, description, and recent JDs.

    Returns:
        company_data enriched with vendor_friendly_score and detected_signals list.
    """
    text_to_scan = " ".join([
        company_data.get("description", ""),
        company_data.get("recent_jd", ""),
        company_data.get("about", ""),
    ]).lower()

    detected = [s for s in VENDOR_FRIENDLY_SIGNALS if s in text_to_scan]
    score = min(1.0, len(detected) * 0.2)

    return {
        **company_data,
        "vendor_friendly_score": round(score, 2),
        "vendor_friendly_signals": detected,
        "is_vendor_friendly": score >= 0.4,
    }


@tool
def classify_company_type(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify a company into one of the platform's industry categories.

    Args:
        company_data: Company information including description and industry tags.

    Returns:
        company_data with 'company_type' and 'secondary_types' fields added.
    """
    desc = (company_data.get("description", "") + " " + company_data.get("industry", "")).lower()
    scores: Dict[str, float] = {}

    keywords: Dict[str, List[str]] = {
        "IT Services": ["it services", "outsourcing", "infosys", "wipro", "tcs", "hcl", "tech mahindra"],
        "BFSI": ["bank", "insurance", "financial services", "nbfc", "fintech", "mutual fund"],
        "Product": ["saas", "product company", "b2b product", "platform"],
        "GCC": ["global capability", "captive center", "gcc", "offshore center"],
        "Startup": ["startup", "series a", "series b", "funded", "seed stage"],
        "HealthIT": ["healthcare", "hospital", "pharma", "medtech", "healthtech"],
        "EdTech": ["edtech", "education technology", "online learning", "e-learning"],
        "FinTech": ["fintech", "payments", "lending", "wealthtech", "insurtech"],
        "Ecomm": ["ecommerce", "marketplace", "retail tech", "d2c"],
        "Telecom": ["telecom", "telecommunications", "network", "5g"],
        "AIML": ["artificial intelligence", "machine learning", "deep learning", "ai company"],
    }

    for ctype, kws in keywords.items():
        scores[ctype] = sum(1 for kw in kws if kw in desc)

    primary = max(scores, key=lambda k: scores[k]) if scores else "IT Services"
    secondary = [k for k, v in scores.items() if v > 0 and k != primary]

    return {
        **company_data,
        "company_type": primary,
        "secondary_types": secondary[:2],
        "classification_scores": scores,
    }


@tool
def extract_company_contacts(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract hiring contacts (HR, TA, Recruiters) from company data.

    Args:
        company_data: Company record possibly containing LinkedIn URLs, website.

    Returns:
        company_data with 'contacts' list added.
    """
    # In production: calls LinkedIn scraper + Apollo + Hunter APIs
    contacts = []
    if company_data.get("linkedin_url"):
        contacts.append({
            "source": "linkedin",
            "lookup_url": company_data["linkedin_url"],
            "roles_to_find": ["HR Manager", "Talent Acquisition", "Recruiter", "HR Business Partner"],
            "status": "pending_enrichment",
        })
    return {**company_data, "contacts": contacts, "contact_extraction_status": "queued"}


@tool
def score_employer_attractiveness(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a composite attractiveness score (0-100) for an employer.

    Factors: vendor friendliness, hiring volume, GCC potential, company type, size, remote policy.

    Args:
        company_data: Enriched company record.

    Returns:
        company_data with 'attractiveness_score' and 'score_breakdown' fields.
    """
    score = 0.0
    breakdown: Dict[str, float] = {}

    # Vendor friendliness (up to 25 pts)
    vf = float(company_data.get("vendor_friendly_score", 0.0))
    breakdown["vendor_friendly"] = round(vf * 25, 1)
    score += breakdown["vendor_friendly"]

    # GCC bonus (15 pts)
    gcc_flag = company_data.get("is_gcc", False)
    breakdown["gcc"] = 15.0 if gcc_flag else 0.0
    score += breakdown["gcc"]

    # Hiring volume (up to 20 pts)
    hiring_vol = min(int(company_data.get("open_positions", 0)), 20)
    breakdown["hiring_volume"] = float(hiring_vol)
    score += breakdown["hiring_volume"]

    # Company type multiplier (up to 15 pts)
    type_scores = {
        "Product": 15, "GCC": 15, "AIML": 14, "FinTech": 13,
        "Startup": 12, "HealthIT": 11, "EdTech": 10, "Ecomm": 10,
        "BFSI": 9, "Telecom": 8, "IT Services": 7,
    }
    ctype = company_data.get("company_type", "IT Services")
    breakdown["company_type"] = float(type_scores.get(ctype, 5))
    score += breakdown["company_type"]

    # Company size bonus (up to 15 pts) — mid-size companies are most likely to use vendors
    size = company_data.get("employee_count", 0)
    if 200 <= size <= 5000:
        breakdown["company_size"] = 15.0
    elif 5000 < size <= 20000:
        breakdown["company_size"] = 10.0
    elif size > 20000:
        breakdown["company_size"] = 5.0
    else:
        breakdown["company_size"] = 8.0
    score += breakdown["company_size"]

    # Remote / hybrid flexibility (up to 10 pts)
    remote = company_data.get("remote_policy", "").lower()
    if "remote" in remote:
        breakdown["remote_policy"] = 10.0
    elif "hybrid" in remote:
        breakdown["remote_policy"] = 7.0
    else:
        breakdown["remote_policy"] = 3.0
    score += breakdown["remote_policy"]

    final_score = min(100.0, round(score, 1))
    return {
        **company_data,
        "attractiveness_score": final_score,
        "score_breakdown": breakdown,
        "priority": "HIGH" if final_score >= 70 else "MEDIUM" if final_score >= 45 else "LOW",
    }


@tool
def detect_gcc_company(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect whether a company is a Global Capability Centre (GCC).

    Args:
        company_data: Company record with description and name.

    Returns:
        company_data enriched with is_gcc flag.
    """
    text = (
        company_data.get("description", "") + " " + company_data.get("name", "")
    ).lower()
    gcc_detected = any(sig in text for sig in GCC_SIGNALS)
    return {**company_data, "is_gcc": gcc_detected}


@tool
def detect_c2h_bench_signals(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect contract-to-hire and bench sales signals specific to the Indian IT ecosystem.

    Args:
        company_data: Company record with JD samples and description.

    Returns:
        company_data with c2h_detected, bench_sales_detected, staffing_aggregator flags.
    """
    jds_text = " ".join(company_data.get("jd_samples", [])).lower()
    desc = company_data.get("description", "").lower()
    combined = jds_text + " " + desc

    c2h_keywords = ["c2h", "contract to hire", "contract-to-hire", "perm after 6 months"]
    bench_keywords = ["bench sales", "bench marketing", "available immediately", "bench resources"]
    staffing_keywords = ["staffing agency", "placement agency", "manpower", "recruitment agency"]

    return {
        **company_data,
        "c2h_detected": any(kw in combined for kw in c2h_keywords),
        "bench_sales_detected": any(kw in combined for kw in bench_keywords),
        "staffing_aggregator": any(kw in combined for kw in staffing_keywords),
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class EmployerDiscoveryAgent(BaseAgent):
    """
    LangGraph agent responsible for discovering and qualifying employers.

    Workflow nodes:
        1. discover_companies  – scrape job boards for active hiring companies
        2. classify_companies  – classify type, GCC, C2H, vendor-friendliness
        3. extract_contacts    – queue contact extraction for top companies
        4. score_employers     – compute attractiveness score
        5. publish_results     – publish to Kafka employer.discovered topic
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="EmployerDiscoveryAgent", **kwargs)
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        workflow = StateGraph(EmployerDiscoveryState)

        workflow.add_node("discover_companies", self._node_discover_companies)
        workflow.add_node("classify_companies", self._node_classify_companies)
        workflow.add_node("extract_contacts", self._node_extract_contacts)
        workflow.add_node("score_employers", self._node_score_employers)
        workflow.add_node("publish_results", self._node_publish_results)

        workflow.set_entry_point("discover_companies")
        workflow.add_edge("discover_companies", "classify_companies")
        workflow.add_edge("classify_companies", "extract_contacts")
        workflow.add_edge("extract_contacts", "score_employers")
        workflow.add_edge("score_employers", "publish_results")
        workflow.add_edge("publish_results", END)

        return workflow.compile()

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------

    async def _node_discover_companies(
        self, state: EmployerDiscoveryState
    ) -> EmployerDiscoveryState:
        """Discover companies from multiple job boards via LLM + scraper."""
        self.log_state_transition("START", "discover_companies", list(state.keys()))
        region = state.get("region", "India")
        role = state.get("target_role", "Java Developer")
        industry = state.get("industry")

        prompt = f"""You are an expert recruitment researcher.

Task: Identify the top 20 companies actively hiring {role} professionals in {region}.
{"Focus on " + industry + " industry." if industry else ""}

For each company provide:
- name: company name
- website: official website URL
- linkedin_url: LinkedIn company page
- industry: primary industry
- description: 1-2 sentence description
- estimated_employee_count: number (integer)
- open_positions: estimated number of open roles for {role}
- remote_policy: remote/hybrid/onsite
- recent_jd: a sample excerpt from a recent job description (if known)
- about: additional company notes relevant to recruitment

Indian ecosystem specifics to consider:
- Identify GCC (Global Capability Centres) like Walmart GCC, JP Morgan CoE, etc.
- Detect C2H (Contract-to-Hire) opportunities
- Flag bench sales companies and staffing aggregators
- Note companies with corp-to-corp (C2C) hiring patterns

Job boards to consider: {", ".join(INDIAN_JOB_BOARDS)}

Respond ONLY with a valid JSON array of company objects. No extra text."""

        try:
            response = await self.invoke_llm([{"role": "user", "content": prompt}])
            # Strip markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            companies = json.loads(cleaned)
            if not isinstance(companies, list):
                companies = []
        except Exception as exc:
            self.logger.error("Company discovery failed: %s", exc)
            companies = []

        self.logger.info("Discovered %d companies for role=%s region=%s", len(companies), role, region)
        return {**state, "raw_companies": companies}

    async def _node_classify_companies(
        self, state: EmployerDiscoveryState
    ) -> EmployerDiscoveryState:
        """Classify each company: type, GCC, C2H, vendor friendliness."""
        self.log_state_transition("discover_companies", "classify_companies", list(state.keys()))
        raw = state.get("raw_companies", [])
        classified = []

        for company in raw:
            enriched = dict(company)
            enriched = detect_vendor_friendly_companies.invoke({"company_data": enriched})
            enriched = classify_company_type.invoke({"company_data": enriched})
            enriched = detect_gcc_company.invoke({"company_data": enriched})
            enriched = detect_c2h_bench_signals.invoke({"company_data": enriched})
            enriched["company_id"] = str(uuid.uuid4())
            classified.append(enriched)

        self.logger.info("Classified %d companies.", len(classified))
        return {**state, "classified_companies": classified}

    async def _node_extract_contacts(
        self, state: EmployerDiscoveryState
    ) -> EmployerDiscoveryState:
        """Queue contact extraction for each classified company."""
        self.log_state_transition("classify_companies", "extract_contacts", list(state.keys()))
        classified = state.get("classified_companies", [])
        contacts_extracted = []

        for company in classified:
            enriched = extract_company_contacts.invoke({"company_data": company})
            contacts_extracted.append(enriched)

        return {**state, "contacts_extracted": contacts_extracted}

    async def _node_score_employers(
        self, state: EmployerDiscoveryState
    ) -> EmployerDiscoveryState:
        """Score each employer's attractiveness for our recruitment efforts."""
        self.log_state_transition("extract_contacts", "score_employers", list(state.keys()))
        companies = state.get("contacts_extracted", [])
        scored = []

        for company in companies:
            scored_company = score_employer_attractiveness.invoke({"company_data": company})
            scored.append(scored_company)

        # Sort by attractiveness_score descending
        scored.sort(key=lambda c: c.get("attractiveness_score", 0), reverse=True)
        self.logger.info("Scored %d employers; top score: %.1f", len(scored), scored[0].get("attractiveness_score", 0) if scored else 0)
        return {**state, "scored_employers": scored}

    async def _node_publish_results(
        self, state: EmployerDiscoveryState
    ) -> EmployerDiscoveryState:
        """Publish discovered employers to Kafka and cache in Redis."""
        self.log_state_transition("score_employers", "publish_results", list(state.keys()))
        scored = state.get("scored_employers", [])
        published = 0

        for company in scored:
            try:
                self.publish_to_kafka(
                    topic=KAFKA_TOPIC_EMPLOYER_DISCOVERED,
                    payload={
                        "company_id": company.get("company_id"),
                        "name": company.get("name"),
                        "company_type": company.get("company_type"),
                        "region": state.get("region"),
                        "attractiveness_score": company.get("attractiveness_score"),
                        "priority": company.get("priority"),
                        "is_vendor_friendly": company.get("is_vendor_friendly"),
                        "is_gcc": company.get("is_gcc"),
                        "c2h_detected": company.get("c2h_detected"),
                        "target_role": state.get("target_role"),
                        "full_data": company,
                    },
                    key=company.get("company_id"),
                )
                published += 1
            except Exception as exc:
                self.logger.error("Failed to publish company %s: %s", company.get("name"), exc)

        self.logger.info("Published %d employers to Kafka topic=%s", published, KAFKA_TOPIC_EMPLOYER_DISCOVERED)
        return {**state, "published_count": published}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        region: str = "India",
        industry: Optional[str] = None,
        target_role: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute the employer discovery workflow.

        Args:
            task: Human-readable task description.
            region: Target geography (default: India).
            industry: Optional industry filter.
            target_role: Specific role to search for (default: Java Developer).

        Returns:
            Dict with scored_employers list, published_count, and token_usage.
        """
        initial_state: EmployerDiscoveryState = {
            "messages": [],
            "task": task,
            "region": region,
            "industry": industry,
            "target_role": target_role or TARGET_ROLES[0],
            "raw_companies": [],
            "classified_companies": [],
            "contacts_extracted": [],
            "scored_employers": [],
            "published_count": 0,
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }

        final_state = await self._graph.ainvoke(initial_state)

        return {
            "scored_employers": final_state.get("scored_employers", []),
            "published_count": final_state.get("published_count", 0),
            "token_usage": self.token_tracker.to_dict(),
            "region": region,
            "target_role": target_role,
        }

    async def process_state(self, state: AgentState) -> AgentState:
        """Wrap the discovery workflow for base-class compatibility."""
        result = await self.run(
            task=state.get("task", "discover employers"),
            region=state.get("metadata", {}).get("region", "India"),
            industry=state.get("metadata", {}).get("industry"),
            target_role=state.get("metadata", {}).get("target_role"),
        )
        return {**state, "result": result, "updated_at": time.time()}

    async def discover_for_all_roles(self, region: str = "India") -> List[Dict[str, Any]]:
        """Run discovery for every target role in a given region."""
        all_results = []
        for role in TARGET_ROLES:
            result = await self.run(
                task=f"Discover {role} employers in {region}",
                region=region,
                target_role=role,
            )
            all_results.extend(result.get("scored_employers", []))
        # Deduplicate by company name
        seen: set = set()
        unique = []
        for emp in all_results:
            name = emp.get("name", "").lower()
            if name not in seen:
                seen.add(name)
                unique.append(emp)
        return unique
