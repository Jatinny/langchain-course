"""
SQLAlchemy ORM models for the CRM service.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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
class PipelineStage(str, enum.Enum):
    PROSPECTING = "prospecting"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    VENDOR_REGISTERED = "vendor_registered"
    ACTIVE = "active"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class SubmissionStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    SHORTLISTED = "shortlisted"
    INTERVIEWING = "interviewing"
    SELECTED = "selected"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"


class EmploymentType(str, enum.Enum):
    PERMANENT = "permanent"
    CONTRACT = "contract"
    C2H = "c2h"  # Contract-to-Hire
    PART_TIME = "part_time"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class ActivityType(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    NOTE = "note"
    STATUS_CHANGE = "status_change"
    SUBMISSION = "submission"
    PLACEMENT = "placement"
    INVOICE = "invoice"


# ---------------------------------------------------------------------------
# EmployerPipeline
# ---------------------------------------------------------------------------
class EmployerPipeline(Base):
    __tablename__ = "employer_pipeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employer_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    stage: Mapped[PipelineStage] = mapped_column(
        Enum(PipelineStage), default=PipelineStage.PROSPECTING, nullable=False
    )
    probability: Mapped[float] = mapped_column(Float, default=0.0)
    expected_placements_per_month: Mapped[float] = mapped_column(Float, default=0.0)
    expected_monthly_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    assigned_to: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    submissions: Mapped[list["CandidateSubmission"]] = relationship(
        "CandidateSubmission", back_populates="employer_pipeline", cascade="all, delete-orphan"
    )
    placements: Mapped[list["Placement"]] = relationship(
        "Placement", back_populates="employer_pipeline"
    )

    def __repr__(self) -> str:
        return f"<EmployerPipeline employer_id={self.employer_id!r} stage={self.stage}>"


# ---------------------------------------------------------------------------
# CandidateSubmission
# ---------------------------------------------------------------------------
class CandidateSubmission(Base):
    __tablename__ = "candidate_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    job_posting_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    employer_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    employer_pipeline_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("employer_pipeline.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.SUBMITTED, nullable=False
    )
    submission_notes: Mapped[str | None] = mapped_column(Text)
    interview_dates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    offer_details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    placement_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("placements.id", ondelete="SET NULL"), nullable=True
    )
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    employer_pipeline: Mapped["EmployerPipeline | None"] = relationship(
        "EmployerPipeline", back_populates="submissions"
    )

    def __repr__(self) -> str:
        return (
            f"<CandidateSubmission id={self.id} candidate={self.candidate_id!r} "
            f"job={self.job_posting_id!r} status={self.status}>"
        )


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------
class Placement(Base):
    __tablename__ = "placements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    employer_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    employer_pipeline_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("employer_pipeline.id", ondelete="SET NULL"), nullable=True
    )
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType), nullable=False
    )
    salary: Mapped[float] = mapped_column(Float, nullable=False)  # Annual CTC in INR
    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)
    commission_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    invoice_status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.DRAFT
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    employer_pipeline: Mapped["EmployerPipeline | None"] = relationship(
        "EmployerPipeline", back_populates="placements"
    )

    def __repr__(self) -> str:
        return (
            f"<Placement id={self.id} candidate={self.candidate_id!r} "
            f"employer={self.employer_id!r} type={self.employment_type}>"
        )


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------
class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Activity id={self.id} type={self.activity_type} "
            f"entity={self.entity_type}:{self.entity_id}>"
        )


# ---------------------------------------------------------------------------
# Note
# ---------------------------------------------------------------------------
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Note id={self.id} entity={self.entity_type}:{self.entity_id}>"
