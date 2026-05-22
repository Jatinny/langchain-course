"""
Candidate Matching Agent
LangGraph-based agent for parsing resumes, extracting skills, computing vector similarity,
and ranking candidates against job descriptions.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Annotated, Dict, List, Optional, Sequence

import numpy as np
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base_agent import AgentState, BaseAgent

# ---------------------------------------------------------------------------
# Skills Taxonomy
# ---------------------------------------------------------------------------

SKILLS_TAXONOMY: Dict[str, List[str]] = {
    "Java Developer": [
        "Java", "Spring Boot", "Spring MVC", "Spring Security", "Hibernate", "JPA",
        "Maven", "Gradle", "JUnit", "Mockito", "REST API", "Microservices",
        "Docker", "Kubernetes", "AWS", "Azure", "PostgreSQL", "MySQL", "Redis",
    ],
    "AI Engineer": [
        "Python", "TensorFlow", "PyTorch", "scikit-learn", "LangChain", "LangGraph",
        "OpenAI", "Hugging Face", "Vector Databases", "Pinecone", "Weaviate",
        "MLflow", "Kubeflow", "FastAPI", "NumPy", "Pandas", "NLP", "LLM",
    ],
    "Cloud Engineer": [
        "AWS", "Azure", "GCP", "Terraform", "Ansible", "Kubernetes", "Docker",
        "Helm", "ArgoCD", "CI/CD", "Jenkins", "GitHub Actions", "CloudFormation",
        "Networking", "VPC", "IAM", "S3", "EC2", "Lambda",
    ],
    "DevOps Engineer": [
        "Docker", "Kubernetes", "Jenkins", "GitLab CI", "GitHub Actions", "Terraform",
        "Ansible", "Prometheus", "Grafana", "ELK Stack", "Bash", "Python",
        "AWS", "Azure", "GCP", "Helm", "ArgoCD", "Linux", "SRE",
    ],
    "Data Engineer": [
        "Python", "Apache Spark", "Apache Kafka", "Airflow", "dbt", "Snowflake",
        "BigQuery", "Redshift", "PostgreSQL", "MySQL", "MongoDB", "Redis",
        "ETL", "Data Pipelines", "AWS Glue", "Azure Data Factory",
    ],
    "Full Stack Developer": [
        "React", "Angular", "Vue.js", "Node.js", "Express", "TypeScript",
        "Python", "Django", "FastAPI", "REST API", "GraphQL", "PostgreSQL",
        "MongoDB", "Redis", "Docker", "AWS", "HTML5", "CSS3",
    ],
    "QA Automation Engineer": [
        "Selenium", "Appium", "Cypress", "Playwright", "TestNG", "JUnit",
        "Python", "Java", "REST Assured", "Postman", "JMeter",
        "BDD", "Cucumber", "Git", "Jenkins", "JIRA",
    ],
    "SAP Consultant": [
        "SAP ABAP", "SAP Fiori", "SAP S/4HANA", "SAP BW", "SAP BTP",
        "SAP MM", "SAP SD", "SAP FI", "SAP CO", "SAP HCM",
        "SAP Basis", "SAP Integration Suite", "OData",
    ],
    "Salesforce Developer": [
        "Apex", "Visualforce", "LWC", "Salesforce CPQ", "Salesforce Service Cloud",
        "Salesforce Sales Cloud", "SOQL", "SOSL", "Integration", "REST API",
        "Mulesoft", "Flow", "Process Builder", "SFDC",
    ],
    "Cybersecurity Engineer": [
        "Penetration Testing", "SIEM", "SOC", "VAPT", "Network Security",
        "Cloud Security", "Identity Management", "Zero Trust", "OWASP",
        "Incident Response", "Threat Intelligence", "Python", "Splunk",
    ],
}

KAFKA_TOPIC_CANDIDATE_MATCHED = "candidate.matched"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class CandidateMatchingState(TypedDict, total=False):
    """State for the CandidateMatchingAgent LangGraph workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    resume_text: Optional[str]
    job_description: Optional[Dict[str, Any]]
    parsed_resume: Optional[Dict[str, Any]]
    extracted_skills: Optional[Dict[str, Any]]
    match_scores: Optional[Dict[str, Any]]
    ranking: List[Dict[str, Any]]
    recruiter_summary: Optional[str]
    recommended_jobs: List[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def parse_resume(resume_text: str) -> Dict[str, Any]:
    """
    Parse raw resume text into structured fields.

    Args:
        resume_text: Plain-text or extracted resume content.

    Returns:
        Structured dict with name, email, phone, experience_years, education,
        current_company, current_role, notice_period, expected_ctc, location.
    """
    # In production: uses LLM extraction – placeholder returns structure
    return {
        "parse_status": "pending_llm_extraction",
        "raw_text": resume_text[:500] + "..." if len(resume_text) > 500 else resume_text,
        "extracted_fields": [
            "name", "email", "phone", "experience_years", "education",
            "current_company", "current_role", "notice_period",
            "expected_ctc", "location", "skills", "certifications",
        ],
    }


@tool
def extract_skills(parsed_resume: Dict[str, Any], target_role: str = "Java Developer") -> Dict[str, Any]:
    """
    Extract and categorise skills from a parsed resume.

    Args:
        parsed_resume: Output from parse_resume.
        target_role: Role to benchmark skills against.

    Returns:
        Dict with matched_skills, missing_skills, skill_coverage_pct, skill_level_map.
    """
    required = SKILLS_TAXONOMY.get(target_role, [])
    resume_skills = parsed_resume.get("skills", [])
    if isinstance(resume_skills, str):
        resume_skills = [s.strip() for s in resume_skills.split(",")]

    matched = [s for s in required if any(s.lower() in rs.lower() for rs in resume_skills)]
    missing = [s for s in required if s not in matched]
    coverage = round(len(matched) / len(required) * 100, 1) if required else 0.0

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "total_required": len(required),
        "matched_count": len(matched),
        "skill_coverage_pct": coverage,
        "target_role": target_role,
    }


@tool
def compute_embedding_similarity(text_a: str, text_b: str) -> float:
    """
    Compute cosine similarity between two texts using OpenAI embeddings.

    Args:
        text_a: First text (e.g. resume summary).
        text_b: Second text (e.g. job description).

    Returns:
        Cosine similarity score between 0.0 and 1.0.
    """
    # In production: uses OpenAIEmbeddings().embed_query() and actual cosine similarity
    # Placeholder returns a deterministic score based on word overlap
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return round(len(intersection) / len(union), 4)


@tool
def score_candidate_job_fit(
    skills_result: Dict[str, Any],
    resume_data: Dict[str, Any],
    job_data: Dict[str, Any],
    embedding_similarity: float,
) -> Dict[str, Any]:
    """
    Compute a composite match score (0-100) for a candidate-job pair.

    Args:
        skills_result: Output from extract_skills.
        resume_data: Parsed resume dictionary.
        job_data: Job description dictionary.
        embedding_similarity: Cosine similarity from compute_embedding_similarity.

    Returns:
        Dict with total_score (0-100), score_breakdown, and recommendation.
    """
    breakdown: Dict[str, float] = {}

    # Skill coverage (40 pts)
    coverage = float(skills_result.get("skill_coverage_pct", 0.0))
    breakdown["skill_match"] = round(coverage * 0.4, 1)

    # Semantic similarity (25 pts)
    breakdown["semantic_similarity"] = round(embedding_similarity * 25, 1)

    # Experience match (20 pts)
    req_exp = int(job_data.get("min_experience_years", 0))
    candidate_exp = int(resume_data.get("experience_years", 0))
    if candidate_exp >= req_exp:
        exp_score = min(20.0, 20.0 * (candidate_exp / max(req_exp, 1)))
    else:
        exp_score = max(0.0, 20.0 - (req_exp - candidate_exp) * 5)
    breakdown["experience"] = round(min(20.0, exp_score), 1)

    # Location match (10 pts)
    job_loc = job_data.get("location", "").lower()
    candidate_loc = resume_data.get("location", "").lower()
    remote = "remote" in job_loc or job_data.get("is_remote", False)
    loc_score = 10.0 if remote or (job_loc and candidate_loc and job_loc in candidate_loc) else 5.0
    breakdown["location"] = loc_score

    # Notice period fit (5 pts)
    notice = resume_data.get("notice_period", "").lower()
    urgency = job_data.get("urgency", "normal").lower()
    if urgency == "urgent" and "immediate" in notice:
        breakdown["notice_period"] = 5.0
    elif "30 days" in notice or "1 month" in notice:
        breakdown["notice_period"] = 4.0
    else:
        breakdown["notice_period"] = 2.0

    total = sum(breakdown.values())
    total = min(100.0, round(total, 1))

    return {
        "total_score": total,
        "score_breakdown": breakdown,
        "grade": "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D",
        "recommendation": "Strong Match" if total >= 80 else "Good Match" if total >= 65 else "Partial Match" if total >= 50 else "Weak Match",
    }


@tool
def generate_recruiter_summary(
    resume_data: Dict[str, Any],
    match_score: Dict[str, Any],
    job_data: Dict[str, Any],
) -> str:
    """
    Generate a recruiter-facing candidate summary for quick screening.

    Args:
        resume_data: Parsed resume data.
        match_score: Output from score_candidate_job_fit.
        job_data: Job description data.

    Returns:
        Formatted summary string for recruiter use.
    """
    name = resume_data.get("name", "Candidate")
    exp = resume_data.get("experience_years", "N/A")
    role = resume_data.get("current_role", "N/A")
    company = resume_data.get("current_company", "N/A")
    skills = resume_data.get("skills", [])
    if isinstance(skills, list):
        top_skills = ", ".join(skills[:5])
    else:
        top_skills = str(skills)[:100]

    score = match_score.get("total_score", 0)
    grade = match_score.get("grade", "C")
    recommendation = match_score.get("recommendation", "Partial Match")

    return (
        f"[{grade}] {name} | {exp} yrs | {role} at {company}\n"
        f"Match Score: {score}/100 – {recommendation}\n"
        f"Top Skills: {top_skills}\n"
        f"Location: {resume_data.get('location', 'N/A')} | "
        f"Notice: {resume_data.get('notice_period', 'N/A')} | "
        f"Expected CTC: {resume_data.get('expected_ctc', 'N/A')}\n"
        f"Applying for: {job_data.get('title', 'N/A')} at {job_data.get('company', 'N/A')}"
    )


@tool
def recommend_jobs(
    resume_data: Dict[str, Any],
    available_jobs: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Recommend the top N jobs for a candidate based on their profile.

    Args:
        resume_data: Parsed candidate data.
        available_jobs: List of open job postings.
        top_n: Number of recommendations to return.

    Returns:
        Sorted list of job recommendations with fit_score.
    """
    scored_jobs = []
    candidate_skills = set(s.lower() for s in resume_data.get("skills", []))

    for job in available_jobs:
        required = set(s.lower() for s in job.get("required_skills", []))
        overlap = len(candidate_skills & required)
        fit = overlap / len(required) * 100 if required else 0.0
        scored_jobs.append({**job, "fit_score": round(fit, 1)})

    scored_jobs.sort(key=lambda j: j.get("fit_score", 0), reverse=True)
    return scored_jobs[:top_n]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CandidateMatchingAgent(BaseAgent):
    """
    LangGraph agent for matching candidates to jobs using NLP + vector similarity.

    Workflow:
        parse_resume -> extract_skills -> compute_match_scores ->
        rank_candidates -> generate_summaries -> END
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="CandidateMatchingAgent", **kwargs)
        self._embeddings: Optional[OpenAIEmbeddings] = None
        self._graph = self._build_graph()

    def _get_embeddings(self) -> OpenAIEmbeddings:
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=self._openai_api_key or None,
            )
        return self._embeddings

    def _build_graph(self) -> Any:
        workflow = StateGraph(CandidateMatchingState)
        workflow.add_node("parse_resume", self._node_parse_resume)
        workflow.add_node("extract_skills", self._node_extract_skills)
        workflow.add_node("compute_match_scores", self._node_compute_match_scores)
        workflow.add_node("rank_candidates", self._node_rank_candidates)
        workflow.add_node("generate_summaries", self._node_generate_summaries)

        workflow.set_entry_point("parse_resume")
        workflow.add_edge("parse_resume", "extract_skills")
        workflow.add_edge("extract_skills", "compute_match_scores")
        workflow.add_edge("compute_match_scores", "rank_candidates")
        workflow.add_edge("rank_candidates", "generate_summaries")
        workflow.add_edge("generate_summaries", END)
        return workflow.compile()

    async def _node_parse_resume(self, state: CandidateMatchingState) -> CandidateMatchingState:
        self.log_state_transition("START", "parse_resume", list(state.keys()))
        resume_text = state.get("resume_text", "")
        if not resume_text:
            return {**state, "parsed_resume": {}, "error": "No resume text provided"}

        prompt = f"""Extract structured information from the following resume.

Resume Text:
---
{resume_text[:3000]}
---

Return a JSON object with these exact fields:
{{
  "name": "full name",
  "email": "email address",
  "phone": "phone number",
  "experience_years": <integer>,
  "education": "highest degree and institution",
  "current_company": "current employer",
  "current_role": "current job title",
  "notice_period": "notice period (e.g. 30 days, immediate)",
  "expected_ctc": "expected salary",
  "location": "current city, country",
  "skills": ["skill1", "skill2", ...],
  "certifications": ["cert1", ...],
  "previous_companies": ["company1", ...]
}}

Respond ONLY with valid JSON. No extra text."""

        try:
            response = await self.invoke_llm([{"role": "user", "content": prompt}])
            cleaned = response.strip().lstrip("```json").lstrip("```").rstrip("```")
            parsed = json.loads(cleaned)
        except Exception as exc:
            self.logger.error("Resume parsing failed: %s", exc)
            parsed = parse_resume.invoke({"resume_text": resume_text})

        return {**state, "parsed_resume": parsed}

    async def _node_extract_skills(self, state: CandidateMatchingState) -> CandidateMatchingState:
        self.log_state_transition("parse_resume", "extract_skills", list(state.keys()))
        parsed = state.get("parsed_resume", {})
        job = state.get("job_description", {})
        target_role = job.get("title", "Java Developer")

        skills_result = extract_skills.invoke({
            "parsed_resume": parsed,
            "target_role": target_role,
        })
        return {**state, "extracted_skills": skills_result}

    async def _node_compute_match_scores(self, state: CandidateMatchingState) -> CandidateMatchingState:
        self.log_state_transition("extract_skills", "compute_match_scores", list(state.keys()))
        parsed = state.get("parsed_resume", {})
        job = state.get("job_description", {})
        skills_result = state.get("extracted_skills", {})

        # Compute semantic similarity
        resume_summary = " ".join([
            parsed.get("current_role", ""),
            " ".join(parsed.get("skills", [])),
        ])
        jd_text = " ".join([
            job.get("title", ""),
            job.get("description", ""),
            " ".join(job.get("required_skills", [])),
        ])

        try:
            embeddings = self._get_embeddings()
            emb_a, emb_b = await asyncio.gather(
                embeddings.aembed_query(resume_summary[:500]),
                embeddings.aembed_query(jd_text[:500]),
            )
            arr_a = np.array(emb_a)
            arr_b = np.array(emb_b)
            similarity = float(np.dot(arr_a, arr_b) / (np.linalg.norm(arr_a) * np.linalg.norm(arr_b) + 1e-9))
        except Exception as exc:
            self.logger.warning("Embedding similarity failed, using Jaccard: %s", exc)
            similarity = compute_embedding_similarity.invoke({"text_a": resume_summary, "text_b": jd_text})

        match_scores = score_candidate_job_fit.invoke({
            "skills_result": skills_result,
            "resume_data": parsed,
            "job_data": job,
            "embedding_similarity": similarity,
        })
        return {**state, "match_scores": match_scores}

    async def _node_rank_candidates(self, state: CandidateMatchingState) -> CandidateMatchingState:
        self.log_state_transition("compute_match_scores", "rank_candidates", list(state.keys()))
        scores = state.get("match_scores", {})
        parsed = state.get("parsed_resume", {})

        ranking_entry = {
            "candidate_id": str(uuid.uuid4()),
            "name": parsed.get("name", "Unknown"),
            "total_score": scores.get("total_score", 0),
            "grade": scores.get("grade", "D"),
            "recommendation": scores.get("recommendation", "Weak Match"),
            "score_breakdown": scores.get("score_breakdown", {}),
        }
        return {**state, "ranking": [ranking_entry]}

    async def _node_generate_summaries(self, state: CandidateMatchingState) -> CandidateMatchingState:
        self.log_state_transition("rank_candidates", "generate_summaries", list(state.keys()))
        summary = generate_recruiter_summary.invoke({
            "resume_data": state.get("parsed_resume", {}),
            "match_score": state.get("match_scores", {}),
            "job_data": state.get("job_description", {}),
        })

        try:
            self.publish_to_kafka(
                topic=KAFKA_TOPIC_CANDIDATE_MATCHED,
                payload={
                    "session_id": state.get("session_id"),
                    "candidate_name": state.get("parsed_resume", {}).get("name"),
                    "job_title": state.get("job_description", {}).get("title"),
                    "match_score": state.get("match_scores", {}).get("total_score"),
                    "grade": state.get("match_scores", {}).get("grade"),
                },
            )
        except Exception as exc:
            self.logger.warning("Could not publish to Kafka: %s", exc)

        return {**state, "recruiter_summary": summary}

    async def run(
        self,
        task: str,
        resume_text: Optional[str] = None,
        job_description: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Match a candidate's resume against a job description."""
        initial_state: CandidateMatchingState = {
            "messages": [],
            "task": task,
            "resume_text": resume_text or "",
            "job_description": job_description or {},
            "parsed_resume": None,
            "extracted_skills": None,
            "match_scores": None,
            "ranking": [],
            "recruiter_summary": None,
            "recommended_jobs": [],
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }
        final_state = await self._graph.ainvoke(initial_state)
        return {
            "parsed_resume": final_state.get("parsed_resume"),
            "extracted_skills": final_state.get("extracted_skills"),
            "match_scores": final_state.get("match_scores"),
            "ranking": final_state.get("ranking", []),
            "recruiter_summary": final_state.get("recruiter_summary"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "match candidate"),
            resume_text=meta.get("resume_text"),
            job_description=meta.get("job_description"),
        )
        return {**state, "result": result, "updated_at": time.time()}


import asyncio  # noqa: E402 – needed for gather inside class methods
