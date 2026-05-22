"""Company CRUD and management endpoints."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_async_db
from common.logging import get_logger
from services.employer_discovery.models import Employer, HiringContact, JobPosting
from services.employer_discovery.schemas import (
    EmployerCreate,
    EmployerListResponse,
    EmployerResponse,
    EmployerStatsResponse,
    EmployerUpdate,
    HiringContactCreate,
    HiringContactResponse,
    ScoreBreakdown,
)

router = APIRouter(prefix="/companies", tags=["companies"])
logger = get_logger(__name__)


@router.get("", response_model=EmployerListResponse)
async def list_employers(
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    vendor_friendly: Optional[bool] = Query(None),
    min_score: float = Query(0.0),
    max_score: float = Query(100.0),
    accepts_contract: Optional[bool] = Query(None),
    accepts_c2h: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("score"),
    db: AsyncSession = Depends(get_async_db),
) -> EmployerListResponse:
    """List employers with filtering and pagination."""
    query = select(Employer).where(Employer.status != "blacklisted")

    if industry:
        query = query.where(Employer.industry == industry)
    if region:
        query = query.where(Employer.region == region)
    if vendor_friendly is not None:
        query = query.where(Employer.is_vendor_friendly == vendor_friendly)
    if accepts_contract is not None:
        query = query.where(Employer.accepts_contract == accepts_contract)
    if accepts_c2h is not None:
        query = query.where(Employer.accepts_c2h == accepts_c2h)
    if search:
        query = query.where(Employer.name.ilike(f"%{search}%"))
    query = query.where(Employer.score.between(min_score, max_score))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sort and paginate
    sort_col = getattr(Employer, sort_by, Employer.score)
    query = query.order_by(sort_col.desc()).offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    employers = result.scalars().all()

    return EmployerListResponse(
        items=[EmployerResponse.model_validate(e) for e in employers],
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get("/stats/summary", response_model=EmployerStatsResponse)
async def get_employer_stats(db: AsyncSession = Depends(get_async_db)) -> EmployerStatsResponse:
    """Get aggregated employer statistics."""
    result = await db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_vendor_friendly THEN 1 ELSE 0 END) as vendor_friendly,
            SUM(CASE WHEN accepts_contract THEN 1 ELSE 0 END) as contract_accepting,
            AVG(score) as avg_score,
            SUM(CASE WHEN score >= 75 THEN 1 ELSE 0 END) as high_score_count
        FROM employers WHERE status != 'blacklisted'
    """))
    row = result.fetchone()

    by_industry = await db.execute(text(
        "SELECT industry, COUNT(*) as cnt FROM employers WHERE status != 'blacklisted' GROUP BY industry"
    ))
    by_region = await db.execute(text(
        "SELECT region, COUNT(*) as cnt FROM employers WHERE status != 'blacklisted' GROUP BY region"
    ))

    return EmployerStatsResponse(
        total_employers=row.total or 0,
        vendor_friendly=row.vendor_friendly or 0,
        contract_accepting=row.contract_accepting or 0,
        by_industry={r.industry: r.cnt for r in by_industry.fetchall() if r.industry},
        by_region={r.region: r.cnt for r in by_region.fetchall() if r.region},
        avg_score=float(row.avg_score or 0),
        high_score_count=row.high_score_count or 0,
    )


@router.get("/{employer_id}", response_model=EmployerResponse)
async def get_employer(
    employer_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> EmployerResponse:
    result = await db.execute(select(Employer).where(Employer.id == employer_id))
    employer = result.scalar_one_or_none()
    if not employer:
        raise HTTPException(status_code=404, detail=f"Employer {employer_id} not found")
    return EmployerResponse.model_validate(employer)


@router.post("", response_model=EmployerResponse, status_code=201)
async def create_employer(
    data: EmployerCreate,
    db: AsyncSession = Depends(get_async_db),
) -> EmployerResponse:
    employer = Employer(
        id=str(uuid.uuid4()),
        **data.model_dump(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(employer)
    await db.commit()
    await db.refresh(employer)
    return EmployerResponse.model_validate(employer)


@router.put("/{employer_id}", response_model=EmployerResponse)
async def update_employer(
    employer_id: str,
    data: EmployerUpdate,
    db: AsyncSession = Depends(get_async_db),
) -> EmployerResponse:
    result = await db.execute(select(Employer).where(Employer.id == employer_id))
    employer = result.scalar_one_or_none()
    if not employer:
        raise HTTPException(status_code=404, detail=f"Employer {employer_id} not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employer, field, value)
    employer.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(employer)
    return EmployerResponse.model_validate(employer)


@router.delete("/{employer_id}", status_code=204)
async def delete_employer(
    employer_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    result = await db.execute(select(Employer).where(Employer.id == employer_id))
    employer = result.scalar_one_or_none()
    if not employer:
        raise HTTPException(status_code=404, detail=f"Employer {employer_id} not found")
    await db.delete(employer)
    await db.commit()


@router.get("/{employer_id}/contacts", response_model=List[HiringContactResponse])
async def get_employer_contacts(
    employer_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> List[HiringContactResponse]:
    result = await db.execute(
        select(HiringContact).where(HiringContact.employer_id == employer_id)
    )
    contacts = result.scalars().all()
    return [HiringContactResponse.model_validate(c) for c in contacts]


@router.post("/{employer_id}/score")
async def rescore_employer(
    employer_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Trigger AI re-scoring of an employer."""
    from services.employer_discovery.services.classifier import CompanyClassifier

    result = await db.execute(select(Employer).where(Employer.id == employer_id))
    employer = result.scalar_one_or_none()
    if not employer:
        raise HTTPException(status_code=404, detail=f"Employer {employer_id} not found")

    classifier = CompanyClassifier()
    employer_data = {
        "name": employer.name,
        "industry": employer.industry,
        "website": employer.website,
        "hiring_volume": employer.hiring_volume,
        "is_vendor_friendly": employer.is_vendor_friendly,
        "accepts_contract": employer.accepts_contract,
        "accepts_c2h": employer.accepts_c2h,
    }
    score, breakdown = await classifier.score_employer(employer_data)
    employer.score = score
    employer.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "employer_id": employer_id,
        "score": score,
        "score_breakdown": breakdown,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }
