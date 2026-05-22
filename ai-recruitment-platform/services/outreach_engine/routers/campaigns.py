"""
Campaigns & Outreach router for the Outreach Engine service.
Provides endpoints for campaign management, template CRUD, and AI message generation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    CampaignStatus,
    EmailTemplate,
    FollowUpSequence,
    MessageChannel,
    MessageStatus,
    OutreachCampaign,
    OutreachMessage,
)
from schemas import (
    CampaignAnalytics,
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    FollowUpSequenceCreate,
    FollowUpSequenceOut,
    GenerateCampaignMessagesRequest,
    GenerateCampaignMessagesResponse,
    GenerateMessageRequest,
    GenerateMessageResponse,
    GeneratedMessage,
    OutreachMessageCreate,
    OutreachMessageOut,
    PaginatedCampaigns,
    PaginatedTemplates,
    SendOutreachRequest,
    SendOutreachResponse,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
from services.email_generator import EmailGeneratorService
from services.linkedin_outreach import LinkedInOutreachService
from services.whatsapp_outreach import WhatsAppOutreachService

logger = logging.getLogger("outreach_engine.routers.campaigns")
router = APIRouter()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def get_db(request: Request) -> AsyncSession:
    factory = request.app.state.async_session_factory
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]

_email_svc = EmailGeneratorService()
_linkedin_svc = LinkedInOutreachService()
_whatsapp_svc = WhatsAppOutreachService()


# ---------------------------------------------------------------------------
# Campaign endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/campaigns",
    response_model=CampaignOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new outreach campaign",
)
async def create_campaign(payload: CampaignCreate, db: DbSession) -> CampaignOut:
    campaign = OutreachCampaign(**payload.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    logger.info("Created campaign id=%s name=%r", campaign.id, campaign.name)
    return CampaignOut.model_validate(campaign)


@router.get(
    "/campaigns",
    response_model=PaginatedCampaigns,
    summary="List outreach campaigns",
)
async def list_campaigns(
    db: DbSession,
    status_filter: CampaignStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedCampaigns:
    q = select(OutreachCampaign)
    if status_filter:
        q = q.where(OutreachCampaign.status == status_filter)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_result.scalar_one()

    q = q.order_by(OutreachCampaign.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    campaigns = result.scalars().all()

    return PaginatedCampaigns(
        total=total,
        page=page,
        page_size=page_size,
        items=[CampaignOut.model_validate(c) for c in campaigns],
    )


@router.get(
    "/campaigns/{campaign_id}",
    response_model=CampaignOut,
    summary="Get campaign by ID",
)
async def get_campaign(campaign_id: int, db: DbSession) -> CampaignOut:
    campaign = await _get_campaign_or_404(campaign_id, db)
    return CampaignOut.model_validate(campaign)


@router.post(
    "/campaigns/{campaign_id}/start",
    response_model=CampaignOut,
    summary="Start / resume a campaign",
)
async def start_campaign(campaign_id: int, db: DbSession) -> CampaignOut:
    campaign = await _get_campaign_or_404(campaign_id, db)
    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start campaign in status '{campaign.status}'.",
        )
    campaign.status = CampaignStatus.ACTIVE
    await db.commit()
    await db.refresh(campaign)
    logger.info("Campaign %s started.", campaign_id)
    return CampaignOut.model_validate(campaign)


@router.post(
    "/campaigns/{campaign_id}/pause",
    response_model=CampaignOut,
    summary="Pause an active campaign",
)
async def pause_campaign(campaign_id: int, db: DbSession) -> CampaignOut:
    campaign = await _get_campaign_or_404(campaign_id, db)
    if campaign.status != CampaignStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active campaigns can be paused.",
        )
    campaign.status = CampaignStatus.PAUSED
    await db.commit()
    await db.refresh(campaign)
    logger.info("Campaign %s paused.", campaign_id)
    return CampaignOut.model_validate(campaign)


@router.get(
    "/campaigns/{campaign_id}/analytics",
    response_model=CampaignAnalytics,
    summary="Get campaign analytics",
)
async def campaign_analytics(campaign_id: int, db: DbSession) -> CampaignAnalytics:
    campaign = await _get_campaign_or_404(campaign_id, db)

    # Aggregate message stats
    q = select(OutreachMessage).where(OutreachMessage.campaign_id == campaign_id)
    result = await db.execute(q)
    messages = result.scalars().all()

    counts: dict[str, int] = {
        "sent": 0, "delivered": 0, "opened": 0,
        "replied": 0, "converted": 0, "bounced": 0,
    }
    channel_breakdown: dict[str, dict[str, int]] = {}

    for msg in messages:
        ch = msg.channel.value
        if ch not in channel_breakdown:
            channel_breakdown[ch] = {
                "sent": 0, "opened": 0, "replied": 0, "bounced": 0
            }
        if msg.status in (MessageStatus.SENT, MessageStatus.DELIVERED,
                          MessageStatus.OPENED, MessageStatus.REPLIED):
            counts["sent"] += 1
            channel_breakdown[ch]["sent"] += 1
        if msg.status == MessageStatus.DELIVERED:
            counts["delivered"] += 1
        if msg.status in (MessageStatus.OPENED, MessageStatus.REPLIED):
            counts["opened"] += 1
            channel_breakdown[ch]["opened"] += 1
        if msg.status == MessageStatus.REPLIED:
            counts["replied"] += 1
            channel_breakdown[ch]["replied"] += 1
        if msg.status == MessageStatus.BOUNCED:
            counts["bounced"] += 1
            channel_breakdown[ch]["bounced"] += 1

    sent = counts["sent"] or 1  # avoid division by zero
    return CampaignAnalytics(
        campaign_id=campaign_id,
        total_contacts=campaign.total_contacts,
        sent_count=counts["sent"],
        delivered_count=counts["delivered"],
        opened_count=counts["opened"],
        replied_count=counts["replied"],
        converted_count=counts["converted"],
        bounced_count=counts["bounced"],
        open_rate=round(counts["opened"] / sent * 100, 2),
        reply_rate=round(counts["replied"] / sent * 100, 2),
        conversion_rate=round(counts["converted"] / sent * 100, 2),
        bounce_rate=round(counts["bounced"] / sent * 100, 2),
        channel_breakdown=channel_breakdown,
        top_performing_template=None,
    )


@router.post(
    "/campaigns/{campaign_id}/generate-messages",
    response_model=GenerateCampaignMessagesResponse,
    summary="AI-generate outreach messages for all contacts in a campaign",
)
async def generate_campaign_messages(
    campaign_id: int,
    payload: GenerateCampaignMessagesRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> GenerateCampaignMessagesResponse:
    campaign = await _get_campaign_or_404(campaign_id, db)

    generated_messages: list[OutreachMessageOut] = []
    failed_contacts: list[str] = []

    for contact in payload.contacts:
        try:
            result = await _email_svc.generate_cold_email(
                contact=contact.model_dump(),
                company=contact.company or "Unknown",
                role=payload.role or campaign.target_role or "your open role",
                jd_summary=payload.jd_summary or "",
            )
            msg = OutreachMessage(
                campaign_id=campaign_id,
                contact_id=contact.id,
                channel=MessageChannel.EMAIL,
                subject=result["subject"],
                body=result["body"],
                status=MessageStatus.PENDING,
                ai_generated=True,
            )
            db.add(msg)
        except Exception as exc:
            logger.warning("Failed to generate message for contact %s: %s", contact.id, exc)
            failed_contacts.append(contact.id)

    # Update contact count
    campaign.total_contacts = len(payload.contacts)
    await db.commit()

    # Refresh and collect
    result_q = await db.execute(
        select(OutreachMessage).where(OutreachMessage.campaign_id == campaign_id)
    )
    saved_msgs = result_q.scalars().all()
    generated_messages = [OutreachMessageOut.model_validate(m) for m in saved_msgs]

    return GenerateCampaignMessagesResponse(
        campaign_id=campaign_id,
        total_generated=len(generated_messages),
        messages=generated_messages,
        failed_contacts=failed_contacts,
    )


# ---------------------------------------------------------------------------
# Single outreach send
# ---------------------------------------------------------------------------
@router.post(
    "/outreach/send",
    response_model=SendOutreachResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a single outreach message",
)
async def send_outreach(payload: SendOutreachRequest, db: DbSession) -> SendOutreachResponse:
    msg = OutreachMessage(
        campaign_id=payload.campaign_id,
        contact_id=payload.contact.id,
        channel=payload.channel,
        subject=payload.subject,
        body=payload.body,
        status=MessageStatus.QUEUED,
        ai_generated=False,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    provider_id: str | None = None
    scheduled_at: datetime | None = payload.schedule_at

    if not payload.schedule_at:
        # Send immediately based on channel
        try:
            if payload.channel == MessageChannel.EMAIL:
                # In production wire to SendGrid / SES
                msg.status = MessageStatus.SENT
                msg.sent_at = datetime.now(timezone.utc)
                provider_id = f"email-{msg.id}"
            elif payload.channel == MessageChannel.WHATSAPP:
                send_result = await _whatsapp_svc.send_message(
                    phone=payload.contact.phone or "",
                    template="custom",
                    params={"body": payload.body},
                )
                msg.status = MessageStatus.SENT
                msg.sent_at = datetime.now(timezone.utc)
                provider_id = send_result.get("message_id")
            elif payload.channel == MessageChannel.LINKEDIN:
                msg.status = MessageStatus.QUEUED  # LinkedIn requires OAuth flow
            await db.commit()
        except Exception as exc:
            logger.error("Failed to send message id=%s: %s", msg.id, exc)
            msg.status = MessageStatus.FAILED
            await db.commit()

    return SendOutreachResponse(
        message_id=msg.id,
        status=msg.status,
        scheduled_at=scheduled_at,
        provider_message_id=provider_id,
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
@router.get(
    "/outreach/templates",
    response_model=PaginatedTemplates,
    summary="List email/message templates",
)
async def list_templates(
    db: DbSession,
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedTemplates:
    from models import TemplateCategory as TC  # local import to avoid circular

    q = select(EmailTemplate).where(EmailTemplate.is_active == True)  # noqa: E712
    if category:
        try:
            q = q.where(EmailTemplate.category == TC(category))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category '{category}'.")

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_result.scalar_one()

    q = q.order_by(EmailTemplate.performance_score.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    templates = result.scalars().all()

    return PaginatedTemplates(
        total=total,
        page=page,
        page_size=page_size,
        items=[TemplateOut.model_validate(t) for t in templates],
    )


@router.post(
    "/outreach/templates",
    response_model=TemplateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new email template",
)
async def create_template(payload: TemplateCreate, db: DbSession) -> TemplateOut:
    # Check uniqueness
    existing = await db.execute(
        select(EmailTemplate).where(EmailTemplate.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{payload.name}' already exists.",
        )

    template = EmailTemplate(**payload.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info("Created template id=%s name=%r", template.id, template.name)
    return TemplateOut.model_validate(template)


# ---------------------------------------------------------------------------
# AI message generation
# ---------------------------------------------------------------------------
@router.post(
    "/outreach/generate",
    response_model=GenerateMessageResponse,
    summary="Generate AI outreach message from JD and contact data",
)
async def generate_outreach_message(
    payload: GenerateMessageRequest,
) -> GenerateMessageResponse:
    contact_dict = payload.contact.model_dump()
    variants: list[GeneratedMessage] = []
    total_tokens = 0

    for i in range(payload.generate_variants):
        try:
            if payload.channel == MessageChannel.EMAIL:
                result = await _email_svc.generate_cold_email(
                    contact=contact_dict,
                    company=payload.contact.company or "your company",
                    role=payload.role or "the open role",
                    jd_summary=payload.jd_summary or "",
                )
            elif payload.channel == MessageChannel.LINKEDIN:
                result = await _linkedin_svc.generate_connection_request(
                    contact=contact_dict,
                    reason=f"Opportunity: {payload.role}",
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="WhatsApp generation requires a template.",
                )

            spam_score = await _email_svc.compute_anti_spam_score(result.get("body", ""))
            variants.append(
                GeneratedMessage(
                    subject=result.get("subject"),
                    body=result["body"],
                    anti_spam_score=spam_score,
                    estimated_open_rate=_estimate_open_rate(spam_score),
                    variant_index=i + 1,
                    personalization_tokens=result.get("tokens", []),
                )
            )
            total_tokens += result.get("tokens_used", 0)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Generation error for contact %s variant %d: %s", payload.contact.id, i + 1, exc)
            raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    return GenerateMessageResponse(
        contact_id=payload.contact.id,
        channel=payload.channel,
        variants=variants,
        generation_model="gpt-4o",
        tokens_used=total_tokens or None,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_campaign_or_404(campaign_id: int, db: AsyncSession) -> OutreachCampaign:
    result = await db.execute(
        select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found.",
        )
    return campaign


def _estimate_open_rate(spam_score: float) -> float:
    """Rough heuristic: lower spam score → higher open rate estimate."""
    if spam_score <= 2.0:
        return 45.0
    if spam_score <= 4.0:
        return 35.0
    if spam_score <= 6.0:
        return 22.0
    return 12.0
