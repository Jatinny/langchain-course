"""
Pydantic v2 schemas for the CRM service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models import (
    ActivityType,
    EmploymentType,
    InvoiceStatus,
    PipelineStage,
    SubmissionStatus,
)


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# EmployerPipeline
# ---------------------------------------------------------------------------
class EmployerPipelineCreate(BaseModel):
    employer_id: str = Field(..., min_length=1, max_length=100)
    stage: PipelineStage = PipelineStage.PROSPECTING
    probability: float = Field(0.0, ge=0.0, le=100.0)
    expected_placements_per_month: float = Field(0.0, ge=0.0)
    expected_monthly_revenue: float = Field(0.0, ge=0.0)
    assigned_to: str | None = None
    notes: str | None = None


class EmployerPipelineUpdate(BaseModel):
    stage: PipelineStage | None = None
    probability: float | None = Field(None, ge=0.0, le=100.0)
    expected_placements_per_month: float | None = None
    expected_monthly_revenue: float | None = None
    assigned_to: str | None = None
    notes: str | None = None


class StageChangeRequest(BaseModel):
    new_stage: PipelineStage
    reason: str | None = None
    notes: str | None = None


class EmployerPipelineOut(_Base):
    id: int
    employer_id: str
    stage: PipelineStage
    probability: float
    expected_placements_per_month: float
    expected_monthly_revenue: float
    assigned_to: str | None
    notes: str | None
    last_activity_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# CandidateSubmission
# ---------------------------------------------------------------------------
class InterviewSlot(BaseModel):
    date: str  # ISO date string
    time: str
    type: str = "Technical"  # Technical / HR / Manager / Panel
    interviewer: str | None = None
    outcome: str | None = None  # Passed / Failed / Pending


class OfferDetails(BaseModel):
    offered_salary: float
    offered_title: str | None = None
    offer_date: str | None = None
    joining_date: str | None = None
    benefits: list[str] = Field(default_factory=list)
    counter_offer: bool = False


class CandidateSubmissionCreate(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    job_posting_id: str = Field(..., min_length=1)
    employer_id: str = Field(..., min_length=1)
    employer_pipeline_id: int | None = None
    submission_notes: str | None = None


class SubmissionStatusUpdate(BaseModel):
    status: SubmissionStatus
    notes: str | None = None
    interview_slot: InterviewSlot | None = None
    offer_details: OfferDetails | None = None
    feedback: dict[str, Any] | None = None


class CandidateSubmissionOut(_Base):
    id: int
    candidate_id: str
    job_posting_id: str
    employer_id: str
    employer_pipeline_id: int | None
    submitted_at: datetime
    status: SubmissionStatus
    submission_notes: str | None
    interview_dates: list[dict[str, Any]]
    offer_details: dict[str, Any] | None
    placement_id: int | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------
class PlacementCreate(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    employer_id: str = Field(..., min_length=1)
    employer_pipeline_id: int | None = None
    job_title: str = Field(..., min_length=2, max_length=255)
    start_date: datetime | None = None
    end_date: datetime | None = None
    employment_type: EmploymentType
    salary: float = Field(..., gt=0)
    commission_percentage: float = Field(0.0, ge=0.0, le=50.0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "PlacementCreate":
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date.")
        return self


class PlacementOut(_Base):
    id: int
    candidate_id: str
    employer_id: str
    employer_pipeline_id: int | None
    job_title: str
    start_date: datetime | None
    end_date: datetime | None
    employment_type: EmploymentType
    salary: float
    commission_amount: float
    commission_percentage: float
    invoice_status: InvoiceStatus
    invoice_number: str | None
    paid_amount: float
    payment_date: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------
class RevenueSummary(BaseModel):
    period: str
    total_placements: int
    permanent_placements: int
    contract_placements: int
    c2h_placements: int
    gross_commission: float
    collected_amount: float
    pending_amount: float
    overdue_amount: float
    avg_commission_per_placement: float
    top_employers: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class CRMDashboard(BaseModel):
    pipeline_summary: dict[str, int]  # stage → count
    active_submissions: int
    placements_this_month: int
    revenue_this_month: float
    revenue_pending: float
    conversion_rate: float
    avg_time_to_placement_days: float | None
    top_performing_accounts: list[dict[str, Any]]
    recent_activities: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------
class ActivityCreate(BaseModel):
    entity_type: str = Field(..., pattern="^(employer|candidate|submission|placement)$")
    entity_id: str = Field(..., min_length=1)
    activity_type: ActivityType
    description: str = Field(..., min_length=3, max_length=2000)
    metadata: dict[str, Any] | None = None
    created_by: str | None = None


class ActivityOut(_Base):
    id: int
    entity_type: str
    entity_id: str
    activity_type: ActivityType
    description: str
    metadata_: dict[str, Any] | None = Field(None, alias="metadata_")
    created_by: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Note
# ---------------------------------------------------------------------------
class NoteCreate(BaseModel):
    entity_type: str = Field(..., pattern="^(employer|candidate|submission|placement)$")
    entity_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=3)
    created_by: str | None = None


class NoteOut(_Base):
    id: int
    entity_type: str
    entity_id: str
    content: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------
class PaginatedPipeline(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EmployerPipelineOut]


class PaginatedSubmissions(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CandidateSubmissionOut]


class PaginatedPlacements(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PlacementOut]
