"""
SQLAlchemy ORM models for the Outreach Engine service.
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


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MessageChannel(str, enum.Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"
    OPT_OUT = "opt_out"


class TemplateCategory(str, enum.Enum):
    COLD = "cold"
    PARTNERSHIP = "partnership"
    SUBMISSION = "submission"
    FOLLOWUP = "followup"
    VENDOR_INTRO = "vendor_intro"
    INMAIL = "inmail"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_industry: Mapped[str | None] = mapped_column(String(100))
    target_role: Mapped[str | None] = mapped_column(String(150))
    region: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False
    )
    total_contacts: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    open_rate: Mapped[float] = mapped_column(Float, default=0.0)
    reply_rate: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage", back_populates="campaign", cascade="all, delete-orphan"
    )
    followup_sequences: Mapped[list["FollowUpSequence"]] = relationship(
        "FollowUpSequence", back_populates="campaign", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<OutreachCampaign id={self.id} name={self.name!r} status={self.status}>"


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("outreach_campaigns.id", ondelete="SET NULL"), nullable=True
    )
    contact_id: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(
        Enum(MessageChannel), nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus), default=MessageStatus.PENDING, nullable=False
    )
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    campaign: Mapped["OutreachCampaign | None"] = relationship(
        "OutreachCampaign", back_populates="messages"
    )
    template: Mapped["EmailTemplate | None"] = relationship(
        "EmailTemplate", back_populates="messages"
    )

    def __repr__(self) -> str:
        return (
            f"<OutreachMessage id={self.id} contact={self.contact_id!r} "
            f"channel={self.channel} status={self.status}>"
        )


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    category: Mapped[TemplateCategory] = mapped_column(
        Enum(TemplateCategory), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    performance_score: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    variables: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage", back_populates="template"
    )

    def __repr__(self) -> str:
        return f"<EmailTemplate id={self.id} name={self.name!r} category={self.category}>"


class FollowUpSequence(Base):
    __tablename__ = "followup_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    # JSON array of steps: [{"day": 3, "template_id": 1, "channel": "email"}, ...]
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    campaign: Mapped["OutreachCampaign"] = relationship(
        "OutreachCampaign", back_populates="followup_sequences"
    )

    def __repr__(self) -> str:
        return (
            f"<FollowUpSequence id={self.id} campaign_id={self.campaign_id} "
            f"steps={len(self.steps or [])}>"
        )
