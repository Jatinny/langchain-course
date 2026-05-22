"""
Employer Discovery Service – SQLAlchemy ORM Models
Defines Employer, JobPosting, and HiringContact database models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Employer
# ---------------------------------------------------------------------------

class Employer(Base):
    """
    Represents a company that hires tech talent.
    Central entity linking job postings and hiring contacts.
    """

    __tablename__ = "employers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    industry = Column(String(100), nullable=True, index=True)
    company_type = Column(
        String(50),
        nullable=True,
        comment="IT Services/BFSI/Product/GCC/Startup/HealthIT/EdTech/FinTech/Ecomm/Telecom/AIML",
    )
    size = Column(
        String(50),
        nullable=True,
        comment="1-50/51-200/201-1000/1001-5000/5001-10000/10000+",
    )
    employee_count = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True, index=True)
    country = Column(String(100), nullable=True, default="India", index=True)
    state = Column(String(100), nullable=True)
    website = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    glassdoor_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    tech_stack = Column(ARRAY(String), nullable=True, comment="Known technologies used")
    is_vendor_friendly = Column(Boolean, nullable=True, default=None)
    vendor_friendly_score = Column(Float, nullable=True)
    vendor_friendly_signals = Column(ARRAY(String), nullable=True)
    accepts_contract = Column(Boolean, nullable=True, default=None)
    accepts_c2h = Column(Boolean, nullable=True, default=None, comment="Contract-to-Hire")
    is_gcc = Column(Boolean, nullable=True, default=False, comment="Global Capability Centre")
    is_staffing_aggregator = Column(Boolean, nullable=True, default=False)
    is_bench_sales = Column(Boolean, nullable=True, default=False)
    hiring_volume = Column(Integer, nullable=True, comment="Estimated open positions")
    avg_monthly_postings = Column(Float, nullable=True)
    last_hiring_date = Column(DateTime(timezone=True), nullable=True)
    hiring_trend = Column(
        String(20),
        nullable=True,
        comment="growing/stable/shrinking/unknown",
    )
    remote_policy = Column(
        String(20),
        nullable=True,
        comment="remote/hybrid/onsite",
    )
    funding_stage = Column(String(50), nullable=True)
    contact_count = Column(Integer, nullable=True, default=0)
    score = Column(Float, nullable=True, default=0.0, index=True)
    score_breakdown = Column(JSONB, nullable=True)
    priority = Column(String(10), nullable=True, comment="HIGH/MEDIUM/LOW")
    status = Column(
        String(30),
        nullable=False,
        default="discovered",
        index=True,
        comment="discovered/qualified/contacted/responded/placed/inactive",
    )
    source_platform = Column(String(100), nullable=True)
    source_url = Column(String(1000), nullable=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    job_postings = relationship(
        "JobPosting",
        back_populates="employer",
        cascade="all, delete-orphan",
        lazy="select",
    )
    hiring_contacts = relationship(
        "HiringContact",
        back_populates="employer",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_employers_score_status", "score", "status"),
        Index("ix_employers_country_industry", "country", "industry"),
        Index("ix_employers_vendor_friendly", "is_vendor_friendly", "score"),
    )

    def __repr__(self) -> str:
        return f"<Employer id={self.id} name={self.name!r} score={self.score}>"


# ---------------------------------------------------------------------------
# JobPosting
# ---------------------------------------------------------------------------

class JobPosting(Base):
    """
    Represents a single job posting scraped from a job board.
    Linked to an employer.
    """

    __tablename__ = "job_postings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid, nullable=False)
    employer_id = Column(
        UUID(as_uuid=False),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    skills_required = Column(ARRAY(String), nullable=True)
    skills_preferred = Column(ARRAY(String), nullable=True)
    location = Column(String(255), nullable=True, index=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True, default="India")
    is_remote = Column(Boolean, nullable=True, default=False)
    is_hybrid = Column(Boolean, nullable=True, default=False)
    job_type = Column(
        String(50),
        nullable=True,
        comment="full_time/contract/contract_to_hire/part_time/internship",
    )
    experience_min_years = Column(Integer, nullable=True)
    experience_max_years = Column(Integer, nullable=True)
    salary_min = Column(BigInteger, nullable=True, comment="Annual CTC in INR")
    salary_max = Column(BigInteger, nullable=True, comment="Annual CTC in INR")
    salary_currency = Column(String(5), nullable=True, default="INR")
    posted_date = Column(DateTime(timezone=True), nullable=True, index=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    source_platform = Column(String(100), nullable=True, index=True)
    source_url = Column(String(1000), nullable=True, unique=True)
    source_job_id = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_vendor_friendly = Column(Boolean, nullable=True)
    is_c2h = Column(Boolean, nullable=True, default=False)
    requires_sponsorship = Column(Boolean, nullable=True, default=False)
    applicant_count = Column(Integer, nullable=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    employer = relationship("Employer", back_populates="job_postings")

    __table_args__ = (
        Index("ix_job_postings_employer_active", "employer_id", "is_active"),
        Index("ix_job_postings_title_location", "title", "location"),
        Index("ix_job_postings_posted_date", "posted_date"),
    )

    def __repr__(self) -> str:
        return f"<JobPosting id={self.id} title={self.title!r} employer_id={self.employer_id}>"


# ---------------------------------------------------------------------------
# HiringContact
# ---------------------------------------------------------------------------

class HiringContact(Base):
    """
    Represents a hiring decision-maker (HR, TA, Recruiter) at an employer.
    Used for personalised outreach.
    """

    __tablename__ = "hiring_contacts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid, nullable=False)
    employer_id = Column(
        UUID(as_uuid=False),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    title = Column(String(255), nullable=True, index=True, comment="Job title e.g. HR Manager")
    department = Column(String(100), nullable=True)
    seniority = Column(
        String(50),
        nullable=True,
        comment="junior/mid/senior/lead/manager/director/vp/c-level",
    )
    email = Column(String(255), nullable=True, index=True)
    email_verified = Column(Boolean, nullable=True, default=False)
    email_verification_source = Column(String(50), nullable=True, comment="hunter/apollo/manual")
    email_verification_date = Column(DateTime(timezone=True), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    phone = Column(String(30), nullable=True)
    whatsapp = Column(String(30), nullable=True)
    location = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
    verification_source = Column(
        String(50),
        nullable=True,
        comment="apollo/hunter/clearbit/rocketreach/linkedin/manual",
    )
    last_contacted = Column(DateTime(timezone=True), nullable=True)
    last_response_date = Column(DateTime(timezone=True), nullable=True)
    contact_count = Column(Integer, nullable=False, default=0)
    response_count = Column(Integer, nullable=False, default=0)
    response_rate = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_unsubscribed = Column(Boolean, nullable=False, default=False)
    tags = Column(ARRAY(String), nullable=True)
    notes = Column(Text, nullable=True)
    raw_enrichment_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    employer = relationship("Employer", back_populates="hiring_contacts")

    __table_args__ = (
        Index("ix_hiring_contacts_employer_active", "employer_id", "is_active"),
        Index("ix_hiring_contacts_email", "email"),
        Index("ix_hiring_contacts_response_rate", "response_rate"),
    )

    def __repr__(self) -> str:
        return (
            f"<HiringContact id={self.id} name={self.name!r} "
            f"email={self.email!r} employer_id={self.employer_id}>"
        )
