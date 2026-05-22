"""
Pydantic v2 schemas for the Candidate Matching service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from models import CandidateStatus, DemandLevel, WorkType


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Education / Experience sub-schemas
# ---------------------------------------------------------------------------
class EducationEntry(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    grade: str | None = None


class WorkExperienceEntry(BaseModel):
    company: str
    title: str
    start_date: str | None = None  # "Jan 2020"
    end_date: str | None = None    # "Mar 2023" or "Present"
    description: str | None = None
    skills_used: list[str] = Field(default_factory=list)
    location: str | None = None


# ---------------------------------------------------------------------------
# Candidate schemas
# ---------------------------------------------------------------------------
class CandidateCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    current_title: str | None = None
    years_experience: float | None = Field(None, ge=0, le=60)
    skills: list[str] = Field(default_factory=list, max_length=100)
    resume_text: str | None = None
    resume_url: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    availability: str | None = None
    salary_expectation_min: int | None = Field(None, ge=0)
    salary_expectation_max: int | None = Field(None, ge=0)
    preferred_work_type: WorkType | None = None
    willing_to_relocate: bool = False
    willing_to_sponsor: bool = False
    education: list[EducationEntry] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_salary_range(self) -> "CandidateCreate":
        if (
            self.salary_expectation_min is not None
            and self.salary_expectation_max is not None
            and self.salary_expectation_min > self.salary_expectation_max
        ):
            raise ValueError("salary_expectation_min cannot exceed salary_expectation_max.")
        return self

    @field_validator("skills")
    @classmethod
    def deduplicate_skills(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(s.strip() for s in v if s.strip()))


class CandidateUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    location: str | None = None
    current_title: str | None = None
    years_experience: float | None = None
    skills: list[str] | None = None
    availability: str | None = None
    salary_expectation_min: int | None = None
    salary_expectation_max: int | None = None
    preferred_work_type: WorkType | None = None
    willing_to_relocate: bool | None = None
    status: CandidateStatus | None = None


class CandidateOut(_Base):
    id: int
    name: str
    email: str
    phone: str | None
    location: str | None
    current_title: str | None
    years_experience: float | None
    skills: list[str]
    resume_url: str | None
    linkedin_url: str | None
    github_url: str | None
    availability: str | None
    salary_expectation_min: int | None
    salary_expectation_max: int | None
    preferred_work_type: WorkType | None
    willing_to_relocate: bool
    willing_to_sponsor: bool
    status: CandidateStatus
    embedding_vector_id: str | None
    certifications: list[str]
    created_at: datetime
    updated_at: datetime


class CandidateSummary(_Base):
    """Lightweight candidate representation for list views."""
    id: int
    name: str
    current_title: str | None
    years_experience: float | None
    location: str | None
    skills: list[str]
    availability: str | None
    status: CandidateStatus


# ---------------------------------------------------------------------------
# JobPosting (external reference schema — not stored in this service)
# ---------------------------------------------------------------------------
class JobPostingRef(BaseModel):
    """Minimal job posting data passed in for matching."""
    id: str = Field(..., description="External job posting ID")
    title: str
    company: str
    location: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    min_experience_years: float | None = None
    max_experience_years: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    work_type: WorkType | None = None
    jd_text: str | None = None
    industry: str | None = None


# ---------------------------------------------------------------------------
# Match schemas
# ---------------------------------------------------------------------------
class MatchScore(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0)
    skill_match_score: float = Field(..., ge=0.0, le=100.0)
    experience_score: float = Field(..., ge=0.0, le=100.0)
    location_score: float = Field(..., ge=0.0, le=100.0)
    salary_score: float = Field(..., ge=0.0, le=100.0)
    semantic_similarity_score: float = Field(..., ge=0.0, le=100.0)


class JobMatchCreate(BaseModel):
    candidate_id: int
    job_posting_id: str
    overall_score: float
    skill_match_score: float
    experience_score: float
    location_score: float
    salary_score: float
    semantic_similarity_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    nice_to_have_skills: list[str]
    recruiter_summary: str | None = None


class JobMatchOut(_Base):
    id: int
    candidate_id: int
    job_posting_id: str
    overall_score: float
    skill_match_score: float
    experience_score: float
    location_score: float
    salary_score: float
    semantic_similarity_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    nice_to_have_skills: list[str]
    recruiter_summary: str | None
    created_at: datetime


class CandidateMatchResult(BaseModel):
    """A single candidate result in a job match search."""
    candidate: CandidateSummary
    match: JobMatchOut
    rank: int


class JobMatchResult(BaseModel):
    """A single job result when matching jobs for a candidate."""
    job_posting_id: str
    job_title: str
    company: str
    match_score: MatchScore
    matched_skills: list[str]
    missing_skills: list[str]
    recruiter_summary: str | None
    rank: int


# ---------------------------------------------------------------------------
# Bulk matching
# ---------------------------------------------------------------------------
class BulkMatchRequest(BaseModel):
    candidate_ids: list[int] = Field(..., min_length=1, max_length=100)
    job_posting: JobPostingRef
    top_n: int = Field(10, ge=1, le=50)


class BulkMatchResponse(BaseModel):
    job_posting_id: str
    total_candidates: int
    top_matches: list[CandidateMatchResult]
    processing_time_ms: float


# ---------------------------------------------------------------------------
# Resume parsing
# ---------------------------------------------------------------------------
class ParseResumeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    normalize_skills: bool = True


class ParsedResumeData(BaseModel):
    name: str | None
    email: str | None
    phone: str | None
    location: str | None
    current_title: str | None
    years_experience: float | None
    skills: list[str]
    education: list[dict[str, Any]]
    work_experience: list[dict[str, Any]]
    certifications: list[str]
    summary: str | None
    github_url: str | None
    linkedin_url: str | None
    raw_text_length: int
    confidence_score: float


# ---------------------------------------------------------------------------
# Skills gap
# ---------------------------------------------------------------------------
class SkillsGapRequest(BaseModel):
    candidate_id: int
    job_posting: JobPostingRef


class SkillsGapResponse(BaseModel):
    candidate_id: int
    job_posting_id: str
    matched_skills: list[str]
    missing_critical_skills: list[str]
    missing_nice_to_have_skills: list[str]
    transferable_skills: list[str]
    recommended_learning: list[dict[str, str]]
    gap_severity: str  # "low", "medium", "high", "critical"
    estimated_upskill_time_weeks: int | None


# ---------------------------------------------------------------------------
# Skills taxonomy
# ---------------------------------------------------------------------------
class SkillsTaxonomyOut(_Base):
    id: int
    skill_name: str
    category: str
    aliases: list[str]
    related_skills: list[str]
    demand_level: DemandLevel
    avg_salary_premium_pct: float


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class PaginatedCandidates(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CandidateSummary]


class CandidateFilters(BaseModel):
    location: str | None = None
    min_experience: float | None = None
    max_experience: float | None = None
    skills: list[str] | None = None
    work_type: WorkType | None = None
    available_only: bool = False
    status: CandidateStatus | None = CandidateStatus.ACTIVE
