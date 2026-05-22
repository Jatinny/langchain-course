"""
CRM Pipeline router.
Employer pipeline management, candidate submissions, placement tracking, revenue reporting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Activity,
    ActivityType,
    CandidateSubmission,
    EmployerPipeline,
    EmploymentType,
    InvoiceStatus,
    Note,
    Placement,
    PipelineStage,
    SubmissionStatus,
)
from schemas import (
    ActivityCreate,
    ActivityOut,
    CRMDashboard,
    CandidateSubmissionCreate,
    CandidateSubmissionOut,
    EmployerPipelineCreate,
    EmployerPipelineOut,
    NoteCreate,
    NoteOut,
    PaginatedPipeline,
    PaginatedPlacements,
    PaginatedSubmissions,
    PlacementCreate,
    PlacementOut,
    RevenueSummary,
    StageChangeRequest,
    SubmissionStatusUpdate,
)
from services.commission_calculator import CommissionCalculator

logger = logging.getLogger("crm_service.routers.pipeline")
router = APIRouter()

_calc = CommissionCalculator()

# ---------------------------------------------------------------------------
# Stage probability defaults
# ---------------------------------------------------------------------------
STAGE_PROBABILITY_DEFAULTS: dict[PipelineStage, float] = {
    PipelineStage.PROSPECTING: 5.0,
    PipelineStage.CONTACTED: 15.0,
    PipelineStage.INTERESTED: 35.0,
    PipelineStage.VENDOR_REGISTERED: 55.0,
    PipelineStage.ACTIVE: 75.0,
    PipelineStage.CLOSED_WON: 100.0,
    PipelineStage.CLOSED_LOST: 0.0,
}


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def get_db(request: Request) -> AsyncSession:
    factory = request.app.state.async_session_factory
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Employer Pipeline
# ---------------------------------------------------------------------------
@router.get(
    "/pipeline/employers",
    response_model=PaginatedPipeline,
    summary="List employer pipeline by stage",
)
async def list_employer_pipeline(
    db: DbSession,
    stage: PipelineStage | None = None,
    assigned_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedPipeline:
    q = select(EmployerPipeline)
    if stage:
        q = q.where(EmployerPipeline.stage == stage)
    if assigned_to:
        q = q.where(EmployerPipeline.assigned_to == assigned_to)

    total_res = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_res.scalar_one()

    q = q.order_by(EmployerPipeline.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    employers = result.scalars().all()

    return PaginatedPipeline(
        total=total, page=page, page_size=page_size,
        items=[EmployerPipelineOut.model_validate(e) for e in employers],
    )


@router.post(
    "/pipeline/employers",
    response_model=EmployerPipelineOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add employer to pipeline",
)
async def create_employer_pipeline(
    payload: EmployerPipelineCreate, db: DbSession
) -> EmployerPipelineOut:
    exists = await db.execute(
        select(EmployerPipeline).where(EmployerPipeline.employer_id == payload.employer_id)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(409, f"Employer '{payload.employer_id}' already in pipeline.")

    ep = EmployerPipeline(**payload.model_dump())
    db.add(ep)
    await db.commit()
    await db.refresh(ep)

    await _log_activity(
        db, "employer", payload.employer_id,
        ActivityType.STATUS_CHANGE,
        f"Employer added to pipeline at stage {payload.stage}.",
    )
    return EmployerPipelineOut.model_validate(ep)


@router.put(
    "/pipeline/employers/{employer_id}/stage",
    response_model=EmployerPipelineOut,
    summary="Move employer to a new pipeline stage",
)
async def update_employer_stage(
    employer_id: str, payload: StageChangeRequest, db: DbSession
) -> EmployerPipelineOut:
    ep = await _get_employer_or_404(employer_id, db)
    old_stage = ep.stage
    ep.stage = payload.new_stage
    ep.probability = STAGE_PROBABILITY_DEFAULTS.get(payload.new_stage, ep.probability)
    ep.last_activity_at = datetime.now(timezone.utc)

    if payload.notes:
        ep.notes = payload.notes

    await db.commit()
    await db.refresh(ep)

    await _log_activity(
        db, "employer", employer_id,
        ActivityType.STATUS_CHANGE,
        f"Stage moved: {old_stage} → {payload.new_stage}. {payload.reason or ''}",
    )
    return EmployerPipelineOut.model_validate(ep)


# ---------------------------------------------------------------------------
# Candidate Submissions
# ---------------------------------------------------------------------------
@router.get(
    "/pipeline/submissions",
    response_model=PaginatedSubmissions,
    summary="List all candidate submissions",
)
async def list_submissions(
    db: DbSession,
    employer_id: str | None = None,
    candidate_id: str | None = None,
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedSubmissions:
    q = select(CandidateSubmission)
    if employer_id:
        q = q.where(CandidateSubmission.employer_id == employer_id)
    if candidate_id:
        q = q.where(CandidateSubmission.candidate_id == candidate_id)
    if status_filter:
        q = q.where(CandidateSubmission.status == status_filter)

    total_res = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_res.scalar_one()

    q = q.order_by(CandidateSubmission.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    submissions = result.scalars().all()

    return PaginatedSubmissions(
        total=total, page=page, page_size=page_size,
        items=[CandidateSubmissionOut.model_validate(s) for s in submissions],
    )


@router.post(
    "/pipeline/submissions",
    response_model=CandidateSubmissionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new candidate submission",
)
async def create_submission(
    payload: CandidateSubmissionCreate, db: DbSession
) -> CandidateSubmissionOut:
    submission = CandidateSubmission(**payload.model_dump())
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # Update employer last_activity
    ep_res = await db.execute(
        select(EmployerPipeline).where(EmployerPipeline.employer_id == payload.employer_id)
    )
    ep = ep_res.scalar_one_or_none()
    if ep:
        ep.last_activity_at = datetime.now(timezone.utc)
        await db.commit()

    await _log_activity(
        db, "employer", payload.employer_id,
        ActivityType.SUBMISSION,
        f"Candidate {payload.candidate_id} submitted for job {payload.job_posting_id}.",
    )
    return CandidateSubmissionOut.model_validate(submission)


@router.put(
    "/pipeline/submissions/{submission_id}/status",
    response_model=CandidateSubmissionOut,
    summary="Update candidate submission status",
)
async def update_submission_status(
    submission_id: int, payload: SubmissionStatusUpdate, db: DbSession
) -> CandidateSubmissionOut:
    result = await db.execute(
        select(CandidateSubmission).where(CandidateSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(404, f"Submission {submission_id} not found.")

    old_status = submission.status
    submission.status = payload.status

    if payload.notes:
        submission.submission_notes = payload.notes

    if payload.interview_slot:
        slots = list(submission.interview_dates or [])
        slots.append(payload.interview_slot.model_dump())
        submission.interview_dates = slots

    if payload.offer_details:
        submission.offer_details = payload.offer_details.model_dump()

    if payload.feedback:
        submission.feedback = payload.feedback

    await db.commit()
    await db.refresh(submission)

    await _log_activity(
        db, "submission", str(submission_id),
        ActivityType.STATUS_CHANGE,
        f"Submission status: {old_status} → {payload.status}.",
    )
    return CandidateSubmissionOut.model_validate(submission)


# ---------------------------------------------------------------------------
# Placements
# ---------------------------------------------------------------------------
@router.post(
    "/pipeline/placements",
    response_model=PlacementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new placement",
)
async def create_placement(payload: PlacementCreate, db: DbSession) -> PlacementOut:
    # Calculate commission
    if payload.employment_type == EmploymentType.PERMANENT:
        commission = _calc.calculate_permanent_placement_fee(
            payload.salary, payload.commission_percentage or 8.33
        )
    elif payload.employment_type == EmploymentType.CONTRACT:
        # For contract: salary = monthly CTC, commission is margin on billing
        commission = _calc.calculate_contract_fee(
            daily_rate=payload.salary / 22,  # ~22 working days/month
            margin_percentage=payload.commission_percentage or 15.0,
        )
    else:
        commission = _calc.calculate_c2h_fee(
            monthly_ctc=payload.salary / 12,
            months_contract=6,
            conversion_fee=payload.salary * 0.05,
        )

    invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{payload.employer_id[:4].upper()}"

    placement = Placement(
        **{k: v for k, v in payload.model_dump().items()},
        commission_amount=commission,
        invoice_status=InvoiceStatus.DRAFT,
        invoice_number=invoice_number,
    )
    db.add(placement)
    await db.commit()
    await db.refresh(placement)

    # Update employer pipeline last activity
    ep_res = await db.execute(
        select(EmployerPipeline).where(EmployerPipeline.employer_id == payload.employer_id)
    )
    ep = ep_res.scalar_one_or_none()
    if ep and ep.stage != PipelineStage.CLOSED_WON:
        ep.stage = PipelineStage.ACTIVE
        ep.last_activity_at = datetime.now(timezone.utc)
        await db.commit()

    await _log_activity(
        db, "employer", payload.employer_id,
        ActivityType.PLACEMENT,
        f"Placement recorded: {payload.job_title} — Commission: ₹{commission:,.0f}",
    )
    logger.info("Placement created id=%s commission=₹%s", placement.id, f"{commission:,.0f}")
    return PlacementOut.model_validate(placement)


@router.get(
    "/pipeline/placements",
    response_model=PaginatedPlacements,
    summary="List placements",
)
async def list_placements(
    db: DbSession,
    employer_id: str | None = None,
    employment_type: EmploymentType | None = None,
    invoice_status: InvoiceStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedPlacements:
    q = select(Placement)
    if employer_id:
        q = q.where(Placement.employer_id == employer_id)
    if employment_type:
        q = q.where(Placement.employment_type == employment_type)
    if invoice_status:
        q = q.where(Placement.invoice_status == invoice_status)

    total_res = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_res.scalar_one()

    q = q.order_by(Placement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    placements = result.scalars().all()

    return PaginatedPlacements(
        total=total, page=page, page_size=page_size,
        items=[PlacementOut.model_validate(p) for p in placements],
    )


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------
@router.get(
    "/pipeline/revenue",
    response_model=RevenueSummary,
    summary="Revenue summary for a given month/year",
)
async def revenue_summary(
    db: DbSession,
    year: int = Query(datetime.now().year),
    month: int = Query(datetime.now().month, ge=1, le=12),
) -> RevenueSummary:
    from sqlalchemy import extract

    q = select(Placement).where(
        and_(
            extract("year", Placement.created_at) == year,
            extract("month", Placement.created_at) == month,
        )
    )
    result = await db.execute(q)
    placements = result.scalars().all()

    total_commission = sum(p.commission_amount for p in placements)
    collected = sum(p.paid_amount for p in placements)
    pending = sum(
        p.commission_amount - p.paid_amount
        for p in placements
        if p.invoice_status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED)
    )
    overdue = sum(
        p.commission_amount - p.paid_amount
        for p in placements
        if p.invoice_status == InvoiceStatus.OVERDUE
    )

    # Top employers by commission
    employer_totals: dict[str, float] = {}
    for p in placements:
        employer_totals[p.employer_id] = employer_totals.get(p.employer_id, 0.0) + p.commission_amount
    top_employers = sorted(
        [{"employer_id": k, "commission": v} for k, v in employer_totals.items()],
        key=lambda x: x["commission"],
        reverse=True,
    )[:5]

    perm_count = sum(1 for p in placements if p.employment_type == EmploymentType.PERMANENT)
    contract_count = sum(1 for p in placements if p.employment_type == EmploymentType.CONTRACT)
    c2h_count = sum(1 for p in placements if p.employment_type == EmploymentType.C2H)

    return RevenueSummary(
        period=f"{year}-{month:02d}",
        total_placements=len(placements),
        permanent_placements=perm_count,
        contract_placements=contract_count,
        c2h_placements=c2h_count,
        gross_commission=round(total_commission, 2),
        collected_amount=round(collected, 2),
        pending_amount=round(pending, 2),
        overdue_amount=round(overdue, 2),
        avg_commission_per_placement=round(total_commission / len(placements), 2) if placements else 0.0,
        top_employers=top_employers,
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@router.get(
    "/pipeline/dashboard",
    response_model=CRMDashboard,
    summary="Complete CRM dashboard data",
)
async def crm_dashboard(db: DbSession) -> CRMDashboard:
    from datetime import date
    from sqlalchemy import extract

    now = datetime.now(timezone.utc)

    # Pipeline stage counts
    stage_res = await db.execute(
        select(EmployerPipeline.stage, func.count()).group_by(EmployerPipeline.stage)
    )
    pipeline_summary = {row[0].value: row[1] for row in stage_res.all()}

    # Active submissions
    active_subs_res = await db.execute(
        select(func.count()).where(
            CandidateSubmission.status.in_([
                SubmissionStatus.SUBMITTED, SubmissionStatus.SHORTLISTED,
                SubmissionStatus.INTERVIEWING,
            ])
        )
    )
    active_submissions: int = active_subs_res.scalar_one()

    # Placements this month
    placements_res = await db.execute(
        select(Placement).where(
            and_(
                extract("year", Placement.created_at) == now.year,
                extract("month", Placement.created_at) == now.month,
            )
        )
    )
    monthly_placements = placements_res.scalars().all()

    monthly_revenue = sum(p.commission_amount for p in monthly_placements)
    pending_revenue_res = await db.execute(
        select(func.sum(Placement.commission_amount - Placement.paid_amount)).where(
            Placement.invoice_status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
        )
    )
    pending_revenue = float(pending_revenue_res.scalar_one() or 0.0)

    # Conversion rate (submitted → selected)
    total_subs_res = await db.execute(select(func.count()).select_from(CandidateSubmission))
    total_subs: int = total_subs_res.scalar_one()
    selected_res = await db.execute(
        select(func.count()).where(
            CandidateSubmission.status.in_([
                SubmissionStatus.SELECTED, SubmissionStatus.OFFER_ACCEPTED,
            ])
        )
    )
    selected: int = selected_res.scalar_one()
    conversion_rate = round(selected / total_subs * 100, 2) if total_subs else 0.0

    # Recent activities
    act_res = await db.execute(
        select(Activity).order_by(Activity.created_at.desc()).limit(10)
    )
    recent_activities = [
        {
            "id": a.id,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "type": a.activity_type.value,
            "description": a.description,
            "created_at": a.created_at.isoformat(),
        }
        for a in act_res.scalars().all()
    ]

    return CRMDashboard(
        pipeline_summary=pipeline_summary,
        active_submissions=active_submissions,
        placements_this_month=len(monthly_placements),
        revenue_this_month=round(monthly_revenue, 2),
        revenue_pending=round(pending_revenue, 2),
        conversion_rate=conversion_rate,
        avg_time_to_placement_days=None,  # Computed in analytics service
        top_performing_accounts=[],
        recent_activities=recent_activities,
    )


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------
@router.post(
    "/pipeline/activities",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log a CRM activity",
)
async def log_activity(payload: ActivityCreate, db: DbSession) -> ActivityOut:
    activity = Activity(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        activity_type=payload.activity_type,
        description=payload.description,
        metadata_=payload.metadata,
        created_by=payload.created_by,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return ActivityOut.model_validate(activity)


@router.get(
    "/pipeline/activities/{entity_type}/{entity_id}",
    response_model=list[ActivityOut],
    summary="Get activities for an entity",
)
async def get_entity_activities(
    entity_type: str,
    entity_id: str,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
) -> list[ActivityOut]:
    result = await db.execute(
        select(Activity)
        .where(and_(Activity.entity_type == entity_type, Activity.entity_id == entity_id))
        .order_by(Activity.created_at.desc())
        .limit(limit)
    )
    activities = result.scalars().all()
    return [ActivityOut.model_validate(a) for a in activities]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
@router.post("/pipeline/notes", response_model=NoteOut, status_code=201, summary="Add a note")
async def add_note(payload: NoteCreate, db: DbSession) -> NoteOut:
    note = Note(**payload.model_dump())
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return NoteOut.model_validate(note)


@router.get(
    "/pipeline/notes/{entity_type}/{entity_id}",
    response_model=list[NoteOut],
    summary="Get notes for an entity",
)
async def get_entity_notes(
    entity_type: str, entity_id: str, db: DbSession
) -> list[NoteOut]:
    result = await db.execute(
        select(Note)
        .where(and_(Note.entity_type == entity_type, Note.entity_id == entity_id))
        .order_by(Note.created_at.desc())
    )
    return [NoteOut.model_validate(n) for n in result.scalars().all()]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_employer_or_404(
    employer_id: str, db: AsyncSession
) -> EmployerPipeline:
    result = await db.execute(
        select(EmployerPipeline).where(EmployerPipeline.employer_id == employer_id)
    )
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(404, f"Employer '{employer_id}' not found in pipeline.")
    return ep


async def _log_activity(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    activity_type: ActivityType,
    description: str,
) -> None:
    try:
        activity = Activity(
            entity_type=entity_type,
            entity_id=str(entity_id),
            activity_type=activity_type,
            description=description,
        )
        db.add(activity)
        await db.flush()
    except Exception as exc:
        logger.warning("Activity logging failed: %s", exc)
