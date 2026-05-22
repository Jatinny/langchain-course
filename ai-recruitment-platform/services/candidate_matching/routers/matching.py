"""
Candidate Matching router.
Provides endpoints for candidate CRUD, resume parsing, and AI-powered job matching.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Candidate, CandidateStatus, JobMatch, SkillsTaxonomy, WorkType
from schemas import (
    BulkMatchRequest,
    BulkMatchResponse,
    CandidateCreate,
    CandidateFilters,
    CandidateMatchResult,
    CandidateOut,
    CandidateSummary,
    CandidateUpdate,
    JobMatchOut,
    JobPostingRef,
    PaginatedCandidates,
    ParseResumeRequest,
    ParsedResumeData,
    SkillsGapRequest,
    SkillsGapResponse,
)
from services.matching_engine import MatchingEngine
from services.resume_parser import ResumeParser
from services.skill_extractor import SkillExtractor

logger = logging.getLogger("candidate_matching.routers.matching")
router = APIRouter()

_matching_engine = MatchingEngine()
_resume_parser = ResumeParser()
_skill_extractor = SkillExtractor()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def get_db(request: Request) -> AsyncSession:
    factory = request.app.state.async_session_factory
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Candidate CRUD
# ---------------------------------------------------------------------------
@router.post(
    "/candidates",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new candidate (optionally with resume file upload)",
)
async def create_candidate(
    payload: CandidateCreate,
    db: DbSession,
) -> CandidateOut:
    # Check duplicate email
    exists = await db.execute(
        select(Candidate).where(Candidate.email == payload.email)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Candidate with email '{payload.email}' already exists.",
        )

    candidate_data = payload.model_dump()
    # Convert nested Pydantic models to dicts
    candidate_data["education"] = [e.model_dump() for e in payload.education]
    candidate_data["work_experience"] = [w.model_dump() for w in payload.work_experience]

    candidate = Candidate(**candidate_data)
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    # Kick off async embedding in background (non-blocking)
    try:
        vector_id = await _matching_engine.create_candidate_embedding(
            candidate_id=candidate.id,
            name=candidate.name,
            skills=candidate.skills,
            experience=candidate.work_experience,
            resume_text=candidate.resume_text or "",
        )
        candidate.embedding_vector_id = vector_id
        await db.commit()
    except Exception as exc:
        logger.warning("Embedding creation failed for candidate %s: %s", candidate.id, exc)

    logger.info("Created candidate id=%s email=%s", candidate.id, candidate.email)
    return CandidateOut.model_validate(candidate)


@router.post(
    "/candidates/upload-resume",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a resume file and auto-create candidate profile",
)
async def upload_resume_and_create(
    db: DbSession,
    file: UploadFile = File(...),
) -> CandidateOut:
    if file.content_type not in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are accepted.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="Resume file must be under 10 MB.")

    try:
        if file.content_type == "application/pdf":
            resume_text = await _resume_parser.parse_pdf(content)
        else:
            resume_text = await _resume_parser.parse_docx(content)

        parsed = await _resume_parser.extract_structured_data(resume_text)
    except Exception as exc:
        logger.error("Resume parsing failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Failed to parse resume: {exc}") from exc

    if not parsed.get("email"):
        raise HTTPException(status_code=422, detail="Could not extract email from resume.")

    # Check duplicate
    exists = await db.execute(
        select(Candidate).where(Candidate.email == parsed["email"])
    )
    if exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Candidate with email '{parsed['email']}' already exists.",
        )

    candidate = Candidate(
        name=parsed.get("name", "Unknown"),
        email=parsed["email"],
        phone=parsed.get("phone"),
        location=parsed.get("location"),
        current_title=parsed.get("current_title"),
        years_experience=parsed.get("years_experience"),
        skills=parsed.get("skills", []),
        resume_text=resume_text,
        education=parsed.get("education", []),
        work_experience=parsed.get("work_experience", []),
        certifications=parsed.get("certifications", []),
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    logger.info("Created candidate from resume upload id=%s", candidate.id)
    return CandidateOut.model_validate(candidate)


@router.get(
    "/candidates",
    response_model=PaginatedCandidates,
    summary="List candidates with filters",
)
async def list_candidates(
    db: DbSession,
    location: str | None = None,
    min_experience: float | None = Query(None, ge=0),
    max_experience: float | None = Query(None, le=60),
    skills: str | None = Query(None, description="Comma-separated skills filter"),
    work_type: WorkType | None = None,
    available_only: bool = False,
    status_filter: CandidateStatus | None = Query(CandidateStatus.ACTIVE, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedCandidates:
    q = select(Candidate)

    if status_filter:
        q = q.where(Candidate.status == status_filter)
    if location:
        q = q.where(Candidate.location.ilike(f"%{location}%"))
    if min_experience is not None:
        q = q.where(Candidate.years_experience >= min_experience)
    if max_experience is not None:
        q = q.where(Candidate.years_experience <= max_experience)
    if work_type:
        q = q.where(Candidate.preferred_work_type == work_type)
    if available_only:
        q = q.where(Candidate.availability.isnot(None))

    # Skill filter (JSON contains, PostgreSQL-specific)
    if skills:
        for skill in skills.split(","):
            skill = skill.strip()
            if skill:
                q = q.where(Candidate.skills.contains([skill]))

    total_res = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_res.scalar_one()

    q = q.order_by(Candidate.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    candidates = result.scalars().all()

    return PaginatedCandidates(
        total=total,
        page=page,
        page_size=page_size,
        items=[CandidateSummary.model_validate(c) for c in candidates],
    )


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateOut,
    summary="Get candidate by ID",
)
async def get_candidate(candidate_id: int, db: DbSession) -> CandidateOut:
    candidate = await _get_candidate_or_404(candidate_id, db)
    return CandidateOut.model_validate(candidate)


@router.get(
    "/candidates/{candidate_id}/summary",
    summary="Get AI-generated recruiter summary for a candidate",
)
async def get_candidate_summary(
    candidate_id: int,
    job_posting_id: str | None = Query(None),
    db: DbSession = Depends(get_db),
) -> dict:
    candidate = await _get_candidate_or_404(candidate_id, db)

    job_ref: JobPostingRef | None = None
    if job_posting_id:
        # Try to find existing match
        match_res = await db.execute(
            select(JobMatch)
            .where(
                and_(
                    JobMatch.candidate_id == candidate_id,
                    JobMatch.job_posting_id == job_posting_id,
                )
            )
        )
        existing_match = match_res.scalar_one_or_none()
        if existing_match and existing_match.recruiter_summary:
            return {
                "candidate_id": candidate_id,
                "job_posting_id": job_posting_id,
                "summary": existing_match.recruiter_summary,
                "cached": True,
            }

    summary = await _matching_engine.generate_standalone_summary(candidate)
    return {
        "candidate_id": candidate_id,
        "summary": summary,
        "cached": False,
    }


# ---------------------------------------------------------------------------
# Matching endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/candidates/{candidate_id}/match-jobs",
    summary="Find matching jobs for a candidate",
)
async def match_jobs_for_candidate(
    candidate_id: int,
    jobs: list[JobPostingRef],
    top_n: int = Query(10, ge=1, le=50),
    db: DbSession = Depends(get_db),
) -> dict:
    if not jobs:
        raise HTTPException(status_code=400, detail="At least one job posting required.")

    candidate = await _get_candidate_or_404(candidate_id, db)
    ranked = await _matching_engine.rank_jobs(candidate=candidate, jobs=jobs)

    results = []
    for rank, (job, score) in enumerate(ranked[:top_n], 1):
        # Persist match
        jm = JobMatch(
            candidate_id=candidate_id,
            job_posting_id=job.id,
            overall_score=score.overall_score,
            skill_match_score=score.skill_match_score,
            experience_score=score.experience_score,
            location_score=score.location_score,
            salary_score=score.salary_score,
            semantic_similarity_score=score.semantic_similarity_score,
            matched_skills=score.matched_skills,
            missing_skills=score.missing_skills,
            nice_to_have_skills=score.nice_to_have_matched,
        )
        db.add(jm)
        results.append(
            {
                "rank": rank,
                "job_posting_id": job.id,
                "job_title": job.title,
                "company": job.company,
                "match_score": score.model_dump(),
                "matched_skills": score.matched_skills,
                "missing_skills": score.missing_skills,
            }
        )

    await db.commit()
    return {"candidate_id": candidate_id, "total_jobs_evaluated": len(jobs), "results": results}


@router.post(
    "/jobs/{job_id}/match-candidates",
    summary="Find matching candidates for a job posting",
)
async def match_candidates_for_job(
    job_id: str,
    job: JobPostingRef,
    top_n: int = Query(10, ge=1, le=50),
    db: DbSession = Depends(get_db),
) -> dict:
    # Fetch active candidates
    result = await db.execute(
        select(Candidate)
        .where(Candidate.status == CandidateStatus.ACTIVE)
        .limit(500)  # pragmatic cap for synchronous scoring
    )
    candidates = result.scalars().all()

    if not candidates:
        return {"job_posting_id": job_id, "total_candidates": 0, "results": []}

    ranked = await _matching_engine.rank_candidates(job=job, candidates=list(candidates))

    results = []
    for rank, (candidate, score) in enumerate(ranked[:top_n], 1):
        summary = await _matching_engine.generate_recruiter_summary(candidate, job, score)

        jm = JobMatch(
            candidate_id=candidate.id,
            job_posting_id=job_id,
            overall_score=score.overall_score,
            skill_match_score=score.skill_match_score,
            experience_score=score.experience_score,
            location_score=score.location_score,
            salary_score=score.salary_score,
            semantic_similarity_score=score.semantic_similarity_score,
            matched_skills=score.matched_skills,
            missing_skills=score.missing_skills,
            recruiter_summary=summary,
        )
        db.add(jm)
        results.append(
            {
                "rank": rank,
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "overall_score": score.overall_score,
                "matched_skills": score.matched_skills,
                "missing_skills": score.missing_skills,
                "recruiter_summary": summary,
            }
        )

    await db.commit()
    return {
        "job_posting_id": job_id,
        "total_candidates_evaluated": len(candidates),
        "results": results,
    }


@router.post(
    "/candidates/bulk-match",
    response_model=BulkMatchResponse,
    summary="Batch match multiple candidates against a job",
)
async def bulk_match(payload: BulkMatchRequest, db: DbSession) -> BulkMatchResponse:
    start = time.perf_counter()

    if not payload.candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids cannot be empty.")

    # Fetch the specified candidates
    result = await db.execute(
        select(Candidate).where(Candidate.id.in_(payload.candidate_ids))
    )
    candidates = result.scalars().all()

    if not candidates:
        raise HTTPException(status_code=404, detail="None of the specified candidates found.")

    ranked = await _matching_engine.rank_candidates(
        job=payload.job_posting, candidates=list(candidates)
    )

    top_matches: list[CandidateMatchResult] = []
    for rank, (candidate, score) in enumerate(ranked[: payload.top_n], 1):
        summary = await _matching_engine.generate_recruiter_summary(
            candidate, payload.job_posting, score
        )
        jm_obj = JobMatch(
            candidate_id=candidate.id,
            job_posting_id=payload.job_posting.id,
            overall_score=score.overall_score,
            skill_match_score=score.skill_match_score,
            experience_score=score.experience_score,
            location_score=score.location_score,
            salary_score=score.salary_score,
            semantic_similarity_score=score.semantic_similarity_score,
            matched_skills=score.matched_skills,
            missing_skills=score.missing_skills,
            recruiter_summary=summary,
        )
        db.add(jm_obj)
        await db.flush()

        top_matches.append(
            CandidateMatchResult(
                candidate=CandidateSummary.model_validate(candidate),
                match=JobMatchOut.model_validate(jm_obj),
                rank=rank,
            )
        )

    await db.commit()
    elapsed_ms = (time.perf_counter() - start) * 1000

    return BulkMatchResponse(
        job_posting_id=payload.job_posting.id,
        total_candidates=len(candidates),
        top_matches=top_matches,
        processing_time_ms=round(elapsed_ms, 2),
    )


# ---------------------------------------------------------------------------
# Resume parsing
# ---------------------------------------------------------------------------
@router.post(
    "/candidates/parse-resume",
    response_model=ParsedResumeData,
    summary="Parse resume text into structured candidate data",
)
async def parse_resume(payload: ParseResumeRequest) -> ParsedResumeData:
    try:
        parsed = await _resume_parser.extract_structured_data(payload.resume_text)

        if payload.normalize_skills:
            parsed["skills"] = await _skill_extractor.normalize_skills(
                parsed.get("skills", [])
            )

        return ParsedResumeData(
            name=parsed.get("name"),
            email=parsed.get("email"),
            phone=parsed.get("phone"),
            location=parsed.get("location"),
            current_title=parsed.get("current_title"),
            years_experience=parsed.get("years_experience"),
            skills=parsed.get("skills", []),
            education=parsed.get("education", []),
            work_experience=parsed.get("work_experience", []),
            certifications=parsed.get("certifications", []),
            summary=parsed.get("summary"),
            github_url=parsed.get("github_url"),
            linkedin_url=parsed.get("linkedin_url"),
            raw_text_length=len(payload.resume_text),
            confidence_score=parsed.get("confidence_score", 0.0),
        )
    except Exception as exc:
        logger.error("Resume parse error: %s", exc)
        raise HTTPException(status_code=422, detail=f"Resume parsing failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Skills gap analysis
# ---------------------------------------------------------------------------
@router.get(
    "/matching/skills-gap",
    response_model=SkillsGapResponse,
    summary="Skills gap analysis between a candidate and a job",
)
async def skills_gap_analysis(
    candidate_id: int,
    job_title: str,
    required_skills: str = Query(..., description="Comma-separated required skills"),
    nice_to_have: str = Query("", description="Comma-separated nice-to-have skills"),
    db: DbSession = Depends(get_db),
) -> SkillsGapResponse:
    candidate = await _get_candidate_or_404(candidate_id, db)

    req_skills = [s.strip() for s in required_skills.split(",") if s.strip()]
    nth_skills = [s.strip() for s in nice_to_have.split(",") if s.strip()]

    job_ref = JobPostingRef(
        id="gap-analysis",
        title=job_title,
        company="",
        required_skills=req_skills,
        nice_to_have_skills=nth_skills,
    )

    overlap = _skill_extractor.compute_skill_overlap(
        candidate_skills=candidate.skills,
        required_skills=req_skills,
    )
    nth_overlap = _skill_extractor.compute_skill_overlap(
        candidate_skills=candidate.skills,
        required_skills=nth_skills,
    )

    missing_critical = overlap["missing"]
    missing_nth = nth_overlap["missing"]
    matched = overlap["matched"]

    # Severity
    if len(missing_critical) == 0:
        severity = "low"
    elif len(missing_critical) <= 2:
        severity = "medium"
    elif len(missing_critical) <= 4:
        severity = "high"
    else:
        severity = "critical"

    # Learning recommendations
    recommendations = [
        {
            "skill": skill,
            "resource": f"Coursera / Udemy course on {skill}",
            "estimated_weeks": "4–8",
        }
        for skill in missing_critical[:5]
    ]

    return SkillsGapResponse(
        candidate_id=candidate_id,
        job_posting_id="gap-analysis",
        matched_skills=matched,
        missing_critical_skills=missing_critical,
        missing_nice_to_have_skills=missing_nth,
        transferable_skills=overlap.get("transferable", []),
        recommended_learning=recommendations,
        gap_severity=severity,
        estimated_upskill_time_weeks=len(missing_critical) * 6 if missing_critical else 0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_candidate_or_404(candidate_id: int, db: AsyncSession) -> Candidate:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate {candidate_id} not found.",
        )
    return candidate
