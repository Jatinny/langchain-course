"""
Pydantic v2 schemas for the Outreach Engine service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from models import CampaignStatus, MessageChannel, MessageStatus, TemplateCategory


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------
class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Contact (external entity — used in request bodies)
# ---------------------------------------------------------------------------
class ContactInfo(BaseModel):
    """Minimal contact information used when generating / sending messages."""

    id: str = Field(..., description="External contact identifier")
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = None
    title: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    timezone: str = Field("Asia/Kolkata", description="IANA timezone string")
    industry: str | None = None
    location: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone number must be between 7 and 15 digits.")
        return v


# ---------------------------------------------------------------------------
# OutreachCampaign schemas
# ---------------------------------------------------------------------------
class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    target_industry: str | None = Field(None, max_length=100)
    target_role: str | None = Field(None, max_length=150)
    region: str | None = Field(None, max_length=100)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Campaign name cannot be blank.")
        return v.strip()


class CampaignUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=255)
    target_industry: str | None = None
    target_role: str | None = None
    region: str | None = None
    status: CampaignStatus | None = None


class CampaignOut(_Base):
    id: int
    name: str
    target_industry: str | None
    target_role: str | None
    region: str | None
    status: CampaignStatus
    total_contacts: int
    sent_count: int
    open_rate: float
    reply_rate: float
    conversion_rate: float
    created_at: datetime
    updated_at: datetime


class CampaignAnalytics(BaseModel):
    campaign_id: int
    total_contacts: int
    sent_count: int
    delivered_count: int
    opened_count: int
    replied_count: int
    converted_count: int
    bounced_count: int
    open_rate: float
    reply_rate: float
    conversion_rate: float
    bounce_rate: float
    channel_breakdown: dict[str, dict[str, int]]
    top_performing_template: str | None


# ---------------------------------------------------------------------------
# OutreachMessage schemas
# ---------------------------------------------------------------------------
class OutreachMessageCreate(BaseModel):
    campaign_id: int | None = None
    contact_id: str = Field(..., min_length=1)
    channel: MessageChannel
    subject: str | None = Field(None, max_length=500)
    body: str = Field(..., min_length=1)
    ai_generated: bool = True
    template_id: int | None = None

    @model_validator(mode="after")
    def subject_required_for_email(self) -> "OutreachMessageCreate":
        if self.channel == MessageChannel.EMAIL and not self.subject:
            raise ValueError("Subject is required for email messages.")
        return self


class OutreachMessageOut(_Base):
    id: int
    campaign_id: int | None
    contact_id: str
    channel: MessageChannel
    subject: str | None
    body: str
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None
    status: MessageStatus
    ai_generated: bool
    template_id: int | None
    created_at: datetime


class SendOutreachRequest(BaseModel):
    contact: ContactInfo
    channel: MessageChannel
    subject: str | None = None
    body: str = Field(..., min_length=1)
    campaign_id: int | None = None
    schedule_at: datetime | None = None


class SendOutreachResponse(BaseModel):
    message_id: int
    status: MessageStatus
    scheduled_at: datetime | None
    provider_message_id: str | None = None


# ---------------------------------------------------------------------------
# EmailTemplate schemas
# ---------------------------------------------------------------------------
class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    category: TemplateCategory
    subject: str = Field(..., min_length=5, max_length=500)
    body: str = Field(..., min_length=20)
    variables: list[str] = Field(default_factory=list)

    @field_validator("variables")
    @classmethod
    def variables_unique(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))  # deduplicate preserving order


class TemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body: str | None = None
    variables: list[str] | None = None
    is_active: bool | None = None


class TemplateOut(_Base):
    id: int
    name: str
    category: TemplateCategory
    subject: str
    body: str
    performance_score: float
    usage_count: int
    variables: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# FollowUpSequence schemas
# ---------------------------------------------------------------------------
class FollowUpStep(BaseModel):
    day: int = Field(..., ge=1, le=365, description="Days after initial send")
    template_id: int | None = None
    channel: MessageChannel = MessageChannel.EMAIL
    custom_subject: str | None = None
    custom_body: str | None = None


class FollowUpSequenceCreate(BaseModel):
    campaign_id: int
    steps: list[FollowUpStep] = Field(..., min_length=1, max_length=10)
    active: bool = True

    @field_validator("steps")
    @classmethod
    def steps_sorted_and_unique(cls, v: list[FollowUpStep]) -> list[FollowUpStep]:
        days = [s.day for s in v]
        if len(days) != len(set(days)):
            raise ValueError("Each follow-up step must have a unique day.")
        return sorted(v, key=lambda s: s.day)


class FollowUpSequenceOut(_Base):
    id: int
    campaign_id: int
    steps: list[dict[str, Any]]
    active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# AI generation request / response schemas
# ---------------------------------------------------------------------------
class GenerateMessageRequest(BaseModel):
    contact: ContactInfo
    channel: MessageChannel = MessageChannel.EMAIL
    jd_summary: str | None = Field(None, max_length=3000)
    role: str | None = None
    company_context: str | None = None
    tone: str = Field("professional", pattern="^(formal|professional|casual|friendly)$")
    generate_variants: int = Field(1, ge=1, le=3)


class GeneratedMessage(BaseModel):
    subject: str | None
    body: str
    anti_spam_score: float = Field(..., ge=0.0, le=10.0)
    estimated_open_rate: float | None = None
    variant_index: int = 1
    personalization_tokens: list[str] = Field(default_factory=list)


class GenerateMessageResponse(BaseModel):
    contact_id: str
    channel: MessageChannel
    variants: list[GeneratedMessage]
    generation_model: str
    tokens_used: int | None = None


class GenerateCampaignMessagesRequest(BaseModel):
    contacts: list[ContactInfo] = Field(..., min_length=1, max_length=500)
    jd_summary: str | None = None
    role: str | None = None
    tone: str = Field("professional", pattern="^(formal|professional|casual|friendly)$")


class GenerateCampaignMessagesResponse(BaseModel):
    campaign_id: int
    total_generated: int
    messages: list[OutreachMessageOut]
    failed_contacts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------
class PaginatedCampaigns(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CampaignOut]


class PaginatedTemplates(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TemplateOut]
