"""
Core Matching Engine
Computes candidate-to-job match scores using skill overlap, experience, location,
salary compatibility, and semantic embedding similarity via Pinecone.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from services.skill_extractor import SkillExtractor

logger = logging.getLogger("candidate_matching.services.matching_engine")

# ---------------------------------------------------------------------------
# Score weights (must sum to 1.0)
# ---------------------------------------------------------------------------
SCORE_WEIGHTS = {
    "skill_match": 0.40,
    "experience": 0.20,
    "semantic_similarity": 0.20,
    "location": 0.10,
    "salary": 0.10,
}

# Cities considered "same metro area" for location scoring
_METRO_GROUPS: list[set[str]] = [
    {"bengaluru", "bangalore"},
    {"mumbai", "thane", "navi mumbai", "pune"},
    {"delhi", "ncr", "gurgaon", "gurugram", "noida", "faridabad"},
    {"hyderabad", "secunderabad", "cyberabad"},
    {"chennai"},
    {"kolkata"},
    {"ahmedabad"},
]


# ---------------------------------------------------------------------------
# MatchScore dataclass
# ---------------------------------------------------------------------------
@dataclass
class MatchScore:
    overall_score: float
    skill_match_score: float
    experience_score: float
    location_score: float
    salary_score: float
    semantic_similarity_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    nice_to_have_matched: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, float]:
        return {
            "overall_score": self.overall_score,
            "skill_match_score": self.skill_match_score,
            "experience_score": self.experience_score,
            "location_score": self.location_score,
            "salary_score": self.salary_score,
            "semantic_similarity_score": self.semantic_similarity_score,
        }


class MatchingEngine:
    """
    AI-powered candidate-to-job matching engine.
    Uses multi-factor scoring + OpenAI embeddings + optional Pinecone vector search.
    """

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            max_retries=3,
        )
        self._embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )
        self._skill_extractor = SkillExtractor()
        self._pinecone_index = self._init_pinecone()
        logger.info("MatchingEngine initialised.")

    # -----------------------------------------------------------------------
    # Pinecone initialisation (optional — graceful degradation)
    # -----------------------------------------------------------------------
    def _init_pinecone(self) -> Any | None:
        api_key = os.getenv("PINECONE_API_KEY", "")
        index_name = os.getenv("PINECONE_INDEX_NAME", "candidates")
        if not api_key:
            logger.warning("PINECONE_API_KEY not set — semantic search disabled.")
            return None
        try:
            from pinecone import Pinecone  # type: ignore[import]

            pc = Pinecone(api_key=api_key)
            return pc.Index(index_name)
        except Exception as exc:
            logger.warning("Pinecone init failed: %s — semantic search disabled.", exc)
            return None

    # -----------------------------------------------------------------------
    # Embedding creation
    # -----------------------------------------------------------------------
    async def create_candidate_embedding(
        self,
        candidate_id: int,
        name: str,
        skills: list[str],
        experience: list[dict[str, Any]],
        resume_text: str,
    ) -> str:
        """
        Create and store an embedding vector for a candidate in Pinecone.
        Returns the Pinecone vector ID.
        """
        text_to_embed = self._build_candidate_text(name, skills, experience, resume_text)
        vector = await self._embeddings.aembed_query(text_to_embed)
        vector_id = f"candidate-{candidate_id}"

        if self._pinecone_index:
            self._pinecone_index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": vector,
                        "metadata": {
                            "candidate_id": candidate_id,
                            "name": name,
                            "skills": skills[:20],
                        },
                    }
                ]
            )

        return vector_id

    # -----------------------------------------------------------------------
    # Overall score computation
    # -----------------------------------------------------------------------
    async def compute_overall_score(
        self, candidate: Any, job: Any
    ) -> MatchScore:
        """
        Compute a multi-factor match score between a candidate and a job posting.

        Args:
            candidate: Candidate ORM model instance.
            job: JobPostingRef Pydantic model.

        Returns MatchScore dataclass.
        """
        # 1. Skill match
        overlap = self._skill_extractor.compute_skill_overlap(
            candidate_skills=getattr(candidate, "skills", []) or [],
            required_skills=getattr(job, "required_skills", []) or [],
        )
        skill_score = overlap["overlap_pct"]
        matched_skills = overlap["matched"]
        missing_skills = overlap["missing"]

        # Nice-to-have overlap
        nth_overlap = self._skill_extractor.compute_skill_overlap(
            candidate_skills=getattr(candidate, "skills", []) or [],
            required_skills=getattr(job, "nice_to_have_skills", []) or [],
        )
        nice_to_have_matched = nth_overlap["matched"]

        # Bonus for nice-to-have coverage (up to 10% boost)
        if nth_overlap["overlap_pct"] > 0:
            skill_score = min(100.0, skill_score + nth_overlap["overlap_pct"] * 0.1)

        # 2. Experience score
        exp_score = self._compute_experience_score(
            candidate_years=getattr(candidate, "years_experience", None),
            min_years=getattr(job, "min_experience_years", None),
            max_years=getattr(job, "max_experience_years", None),
        )

        # 3. Location score
        loc_score = self._compute_location_score(
            candidate_location=getattr(candidate, "location", ""),
            job_location=getattr(job, "location", ""),
            willing_to_relocate=getattr(candidate, "willing_to_relocate", False),
            work_type=getattr(job, "work_type", None),
        )

        # 4. Salary score
        sal_score = self._compute_salary_score(
            candidate_min=getattr(candidate, "salary_expectation_min", None),
            candidate_max=getattr(candidate, "salary_expectation_max", None),
            job_min=getattr(job, "salary_min", None),
            job_max=getattr(job, "salary_max", None),
        )

        # 5. Semantic similarity (embedding-based)
        sem_score = await self._compute_semantic_similarity(candidate, job)

        # Weighted overall score
        overall = (
            skill_score * SCORE_WEIGHTS["skill_match"]
            + exp_score * SCORE_WEIGHTS["experience"]
            + sem_score * SCORE_WEIGHTS["semantic_similarity"]
            + loc_score * SCORE_WEIGHTS["location"]
            + sal_score * SCORE_WEIGHTS["salary"]
        )

        return MatchScore(
            overall_score=round(overall, 2),
            skill_match_score=round(skill_score, 2),
            experience_score=round(exp_score, 2),
            location_score=round(loc_score, 2),
            salary_score=round(sal_score, 2),
            semantic_similarity_score=round(sem_score, 2),
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            nice_to_have_matched=nice_to_have_matched,
        )

    # -----------------------------------------------------------------------
    # Ranking
    # -----------------------------------------------------------------------
    async def rank_candidates(
        self,
        job: Any,
        candidates: list[Any],
    ) -> list[tuple[Any, MatchScore]]:
        """
        Score and rank all candidates for a given job posting.
        Returns sorted list of (candidate, score) tuples, highest score first.
        """
        scored: list[tuple[Any, MatchScore]] = []
        for candidate in candidates:
            try:
                score = await self.compute_overall_score(candidate, job)
                scored.append((candidate, score))
            except Exception as exc:
                logger.warning(
                    "Scoring failed for candidate %s: %s",
                    getattr(candidate, "id", "?"),
                    exc,
                )
        return sorted(scored, key=lambda x: x[1].overall_score, reverse=True)

    async def rank_jobs(
        self,
        candidate: Any,
        jobs: list[Any],
    ) -> list[tuple[Any, MatchScore]]:
        """
        Score and rank all jobs for a given candidate.
        Returns sorted list of (job, score) tuples, highest score first.
        """
        scored: list[tuple[Any, MatchScore]] = []
        for job in jobs:
            try:
                score = await self.compute_overall_score(candidate, job)
                scored.append((job, score))
            except Exception as exc:
                logger.warning(
                    "Scoring failed for job %s: %s",
                    getattr(job, "id", "?"),
                    exc,
                )
        return sorted(scored, key=lambda x: x[1].overall_score, reverse=True)

    # -----------------------------------------------------------------------
    # Recruiter summary generation
    # -----------------------------------------------------------------------
    async def generate_recruiter_summary(
        self,
        candidate: Any,
        job: Any,
        match_score: MatchScore,
    ) -> str:
        """
        Generate a concise AI recruiter summary for a candidate-job match.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a senior recruiter summarising a candidate for a hiring manager. "
                        "Write a 3-4 sentence summary that covers: "
                        "1) why this candidate fits the role, "
                        "2) their strongest matching skills, "
                        "3) any gaps to be aware of, "
                        "4) a hiring recommendation. "
                        "Be specific, professional, and concise."
                    ),
                ),
                (
                    "human",
                    (
                        "Candidate: {name}, {experience} years exp, "
                        "currently {current_title} at {location}\n"
                        "Top Skills: {skills}\n"
                        "Job: {job_title} at {company}\n"
                        "Required Skills: {required_skills}\n"
                        "Match Score: {score:.1f}/100\n"
                        "Matched Skills: {matched}\n"
                        "Missing Skills: {missing}\n"
                        "Write recruiter summary."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm

        response = await chain.ainvoke(
            {
                "name": getattr(candidate, "name", ""),
                "experience": getattr(candidate, "years_experience", "N/A"),
                "current_title": getattr(candidate, "current_title", ""),
                "location": getattr(candidate, "location", "India"),
                "skills": ", ".join((getattr(candidate, "skills", []) or [])[:8]),
                "job_title": getattr(job, "title", ""),
                "company": getattr(job, "company", ""),
                "required_skills": ", ".join((getattr(job, "required_skills", []) or [])[:8]),
                "score": match_score.overall_score,
                "matched": ", ".join(match_score.matched_skills[:6]),
                "missing": ", ".join(match_score.missing_skills[:4]),
            }
        )
        return response.content  # type: ignore[return-value]

    async def generate_standalone_summary(self, candidate: Any) -> str:
        """Generate a general candidate profile summary (without a specific job context)."""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a recruiter writing a concise professional summary for a candidate profile. "
                        "Highlight years of experience, top skills, and career trajectory. "
                        "Max 4 sentences."
                    ),
                ),
                (
                    "human",
                    (
                        "Name: {name}\n"
                        "Current Title: {title}\n"
                        "Experience: {experience} years\n"
                        "Location: {location}\n"
                        "Skills: {skills}\n"
                        "Certifications: {certs}\n"
                        "Write profile summary."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm
        response = await chain.ainvoke(
            {
                "name": getattr(candidate, "name", ""),
                "title": getattr(candidate, "current_title", ""),
                "experience": getattr(candidate, "years_experience", ""),
                "location": getattr(candidate, "location", ""),
                "skills": ", ".join((getattr(candidate, "skills", []) or [])[:10]),
                "certs": ", ".join((getattr(candidate, "certifications", []) or [])[:3]),
            }
        )
        return response.content  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # Internal scoring functions
    # -----------------------------------------------------------------------
    def _compute_experience_score(
        self,
        candidate_years: float | None,
        min_years: float | None,
        max_years: float | None,
    ) -> float:
        if candidate_years is None:
            return 50.0  # Unknown — neutral score

        if min_years is None and max_years is None:
            return 75.0  # No requirement specified

        min_y = min_years or 0.0
        max_y = max_years or 30.0

        if min_y <= candidate_years <= max_y:
            return 100.0
        elif candidate_years < min_y:
            # Underqualified — score decays with gap
            gap = min_y - candidate_years
            return max(0.0, 100.0 - gap * 20)
        else:
            # Overqualified — slight penalty
            excess = candidate_years - max_y
            return max(50.0, 100.0 - excess * 5)

    def _compute_location_score(
        self,
        candidate_location: str | None,
        job_location: str | None,
        willing_to_relocate: bool,
        work_type: str | None,
    ) -> float:
        # Remote jobs — location doesn't matter
        if work_type and work_type.lower() == "remote":
            return 100.0

        if not candidate_location or not job_location:
            return 60.0  # Insufficient data — neutral

        cand_lower = candidate_location.lower()
        job_lower = job_location.lower()

        # Exact city match
        if any(city in cand_lower for city in job_lower.split()) or any(
            city in job_lower for city in cand_lower.split()
        ):
            return 100.0

        # Same metro area
        for metro in _METRO_GROUPS:
            cand_in_metro = any(city in cand_lower for city in metro)
            job_in_metro = any(city in job_lower for city in metro)
            if cand_in_metro and job_in_metro:
                return 90.0

        # Willing to relocate
        if willing_to_relocate:
            return 70.0

        # Different city
        return 30.0

    def _compute_salary_score(
        self,
        candidate_min: int | None,
        candidate_max: int | None,
        job_min: int | None,
        job_max: int | None,
    ) -> float:
        if not any([candidate_min, candidate_max, job_min, job_max]):
            return 75.0  # No data

        cand_mid = self._midpoint(candidate_min, candidate_max)
        job_mid = self._midpoint(job_min, job_max)

        if not cand_mid or not job_mid:
            return 75.0

        # Check overlap between ranges
        c_min = candidate_min or int(cand_mid * 0.9)
        c_max = candidate_max or int(cand_mid * 1.1)
        j_min = job_min or int(job_mid * 0.9)
        j_max = job_max or int(job_mid * 1.1)

        overlap_start = max(c_min, j_min)
        overlap_end = min(c_max, j_max)

        if overlap_start <= overlap_end:
            # Ranges overlap — score based on degree of overlap
            overlap_range = overlap_end - overlap_start
            job_range = j_max - j_min or 1
            return min(100.0, 70.0 + (overlap_range / job_range) * 30)

        # No overlap — score based on how far apart midpoints are
        pct_diff = abs(cand_mid - job_mid) / job_mid
        return max(0.0, 100.0 - pct_diff * 100)

    async def _compute_semantic_similarity(
        self, candidate: Any, job: Any
    ) -> float:
        """Compute cosine similarity between candidate and job embeddings."""
        try:
            cand_text = self._build_candidate_text(
                name=getattr(candidate, "name", ""),
                skills=getattr(candidate, "skills", []) or [],
                experience=getattr(candidate, "work_experience", []) or [],
                resume_text=(getattr(candidate, "resume_text", "") or "")[:2000],
            )
            job_text = self._build_job_text(job)

            cand_vec, job_vec = await asyncio.gather(
                self._embeddings.aembed_query(cand_text),
                self._embeddings.aembed_query(job_text),
            )
            similarity = self._cosine_similarity(cand_vec, job_vec)
            return round(similarity * 100, 2)
        except Exception as exc:
            logger.debug("Semantic similarity computation failed: %s", exc)
            return 50.0  # Fallback neutral score

    # -----------------------------------------------------------------------
    # Text building helpers
    # -----------------------------------------------------------------------
    def _build_candidate_text(
        self,
        name: str,
        skills: list[str],
        experience: list[dict[str, Any]],
        resume_text: str,
    ) -> str:
        skill_str = " ".join(skills[:30])
        exp_str = " ".join(
            f"{e.get('title', '')} at {e.get('company', '')}"
            for e in (experience or [])[:5]
        )
        return f"{name} {skill_str} {exp_str} {resume_text[:1000]}".strip()

    def _build_job_text(self, job: Any) -> str:
        title = getattr(job, "title", "")
        company = getattr(job, "company", "")
        skills = " ".join(
            (getattr(job, "required_skills", []) or [])[:20]
            + (getattr(job, "nice_to_have_skills", []) or [])[:10]
        )
        jd = (getattr(job, "jd_text", "") or "")[:1000]
        return f"{title} {company} {skills} {jd}".strip()

    @staticmethod
    def _midpoint(low: int | None, high: int | None) -> int | None:
        if low is None and high is None:
            return None
        if low is None:
            return high
        if high is None:
            return low
        return (low + high) // 2

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        import math

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


# Lazy asyncio import (avoid top-level import issues in some environments)
import asyncio  # noqa: E402
