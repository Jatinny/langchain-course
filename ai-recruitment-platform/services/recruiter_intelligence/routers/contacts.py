"""Recruiter contact management and enrichment endpoints."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from common.database import get_async_db
from common.logging import get_logger
from services.recruiter_intelligence.models import RecruiterContact, ContactEnrichment
from services.recruiter_intelligence.schemas import (
    RecruiterContactCreate, RecruiterContactResponse, RecruiterContactUpdate,
    ContactListResponse, EnrichmentResult, ContactStatsResponse,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])
logger = get_logger(__name__)


async def enrich_contact_background(contact_id: str) -> None:
    """Background task to enrich a contact via multiple sources."""
    from services.recruiter_intelligence.services.apollo_client import ApolloClient
    from services.recruiter_intelligence.services.hunter_client import HunterClient
    from common.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RecruiterContact).where(RecruiterContact.id == contact_id))
        contact = result.scalar_one_or_none()
        if not contact:
            return

        apollo = ApolloClient()
        hunter = HunterClient()
        enriched = False

        # Try Apollo first
        if contact.email:
            apollo_data = await apollo.enrich_contact(contact.email)
            if apollo_data:
                contact.title = contact.title or apollo_data.get("title")
                contact.phone = contact.phone or apollo_data.get("phone_numbers", [{}])[0].get("sanitized_number")
                contact.linkedin_url = contact.linkedin_url or apollo_data.get("linkedin_url")
                contact.verified_email = True
                contact.verification_source = "apollo"
                enriched = True

                enrich_record = ContactEnrichment(
                    id=str(uuid.uuid4()),
                    contact_id=contact_id,
                    source="apollo",
                    raw_data=apollo_data,
                )
                db.add(enrich_record)

        # Try Hunter.io for email verification
        if contact.email and not enriched:
            verify = await hunter.verify_email(contact.email)
            contact.verified_email = verify.get("verified", False)
            contact.verification_source = "hunter"

            enrich_record = ContactEnrichment(
                id=str(uuid.uuid4()),
                contact_id=contact_id,
                source="hunter",
                raw_data=verify,
            )
            db.add(enrich_record)

        contact.updated_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("Contact enriched", contact_id=contact_id, enriched=enriched)


@router.get("", response_model=ContactListResponse)
async def list_contacts(
    company: Optional[str] = Query(None),
    verified_only: bool = Query(False),
    min_relationship_score: float = Query(0.0),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> ContactListResponse:
    query = select(RecruiterContact)
    if company:
        query = query.where(RecruiterContact.company.ilike(f"%{company}%"))
    if verified_only:
        query = query.where(RecruiterContact.verified_email == True)
    if min_relationship_score > 0:
        query = query.where(RecruiterContact.relationship_score >= min_relationship_score)
    if search:
        query = query.where(
            (RecruiterContact.name.ilike(f"%{search}%")) |
            (RecruiterContact.company.ilike(f"%{search}%"))
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(RecruiterContact.relationship_score.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    contacts = result.scalars().all()

    return ContactListResponse(
        items=[RecruiterContactResponse.model_validate(c) for c in contacts],
        total=total, page=page, limit=limit,
    )


@router.post("", response_model=RecruiterContactResponse, status_code=201)
async def create_contact(
    data: RecruiterContactCreate,
    db: AsyncSession = Depends(get_async_db),
) -> RecruiterContactResponse:
    contact = RecruiterContact(id=str(uuid.uuid4()), **data.model_dump(), created_at=datetime.now(timezone.utc))
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return RecruiterContactResponse.model_validate(contact)


@router.get("/stats", response_model=ContactStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_async_db)) -> ContactStatsResponse:
    from sqlalchemy import text
    row = (await db.execute(text("""
        SELECT COUNT(*) total, SUM(CASE WHEN verified_email THEN 1 ELSE 0 END) verified,
        AVG(response_rate) avg_rr, SUM(placement_count) total_placements,
        AVG(relationship_score) avg_rs FROM recruiter_contacts
    """))).fetchone()
    by_company = dict((await db.execute(text(
        "SELECT company, COUNT(*) cnt FROM recruiter_contacts WHERE company IS NOT NULL GROUP BY company ORDER BY cnt DESC LIMIT 10"
    ))).fetchall())
    return ContactStatsResponse(
        total_contacts=row.total or 0, verified_emails=row.verified or 0,
        avg_response_rate=float(row.avg_rr or 0), total_placements=row.total_placements or 0,
        avg_relationship_score=float(row.avg_rs or 50), by_company=by_company,
    )


@router.get("/{contact_id}", response_model=RecruiterContactResponse)
async def get_contact(contact_id: str, db: AsyncSession = Depends(get_async_db)) -> RecruiterContactResponse:
    result = await db.execute(select(RecruiterContact).where(RecruiterContact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact {contact_id} not found")
    return RecruiterContactResponse.model_validate(contact)


@router.put("/{contact_id}", response_model=RecruiterContactResponse)
async def update_contact(
    contact_id: str, data: RecruiterContactUpdate, db: AsyncSession = Depends(get_async_db),
) -> RecruiterContactResponse:
    result = await db.execute(select(RecruiterContact).where(RecruiterContact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact {contact_id} not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    contact.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(contact)
    return RecruiterContactResponse.model_validate(contact)


@router.post("/{contact_id}/enrich", response_model=dict)
async def enrich_contact(contact_id: str, background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(enrich_contact_background, contact_id)
    return {"contact_id": contact_id, "status": "enrichment_queued"}


@router.post("/bulk-enrich", response_model=dict)
async def bulk_enrich(contact_ids: List[str], background_tasks: BackgroundTasks) -> dict:
    for cid in contact_ids:
        background_tasks.add_task(enrich_contact_background, cid)
    return {"status": "queued", "count": len(contact_ids)}
