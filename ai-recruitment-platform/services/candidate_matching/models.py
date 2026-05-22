"""
SQLAlchemy ORM models for the Candidate Matching service.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CandidateStatus(str, enum.Enum):
    ACTIVE = "active"
    PLACED = "placed"
    INACTIVE = "inactive"
    DO_NOT_CONTACT = "do_not_contact"
    BLACKLISTED = "blacklisted"


class WorkType(str, enum.Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class DemandLevel(str, enum.Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DECLINING = "declining"


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------
class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(150))
    current_title: Mapped[str | None] = mapped_column(String(200))
    years_experience: Mapped[float | None] = mapped_column(Float)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_url: Mapped[str | None] = mapped_column(String(500))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    availability: Mapped[str | None] = mapped_column(String(100))  # e.g. "Immediate", "30 days"
    salary_expectation_min: Mapped[int | None] = mapped_column(Integer)  # INR per annum
    salary_expectation_max: Mapped[int | None] = mapped_column(Integer)
    preferred_work_type: Mapped[WorkType | None] = mapped_column(Enum(WorkType))
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, default=False)
    willing_to_sponsor: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_vector_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.ACTIVE, nullable=False
    )
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    work_experience: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    job_matches: Mapped[list["JobMatch"]] = relationship(
        "JobMatch", back_populates="candidate", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.name!r} title={self.current_title!r}>"


# ---------------------------------------------------------------------------
# JobMatch
# ---------------------------------------------------------------------------
class JobMatch(Base):
    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_posting_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_match_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    location_score: Mapped[float] = mapped_column(Float, default=0.0)
    salary_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    nice_to_have_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    recruiter_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="job_matches")

    def __repr__(self) -> str:
        return (
            f"<JobMatch id={self.id} candidate_id={self.candidate_id} "
            f"job={self.job_posting_id!r} score={self.overall_score:.2f}>"
        )


# ---------------------------------------------------------------------------
# SkillsTaxonomy
# ---------------------------------------------------------------------------
class SkillsTaxonomy(Base):
    __tablename__ = "skills_taxonomy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    related_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    demand_level: Mapped[DemandLevel] = mapped_column(
        Enum(DemandLevel), default=DemandLevel.MEDIUM
    )
    avg_salary_premium_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<SkillsTaxonomy id={self.id} skill={self.skill_name!r} "
            f"category={self.category!r} demand={self.demand_level}>"
        )
