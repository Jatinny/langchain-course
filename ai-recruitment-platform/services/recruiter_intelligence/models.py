"""SQLAlchemy models for recruiter intelligence service."""
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from common.database import Base


class RecruiterContact(Base):
    __tablename__ = "recruiter_contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    company: Mapped[Optional[str]] = mapped_column(String(300))
    company_id: Mapped[Optional[str]] = mapped_column(String(36))
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    verified_email: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_source: Mapped[Optional[str]] = mapped_column(String(50))
    last_contacted: Mapped[Optional[datetime]] = mapped_column(DateTime)
    response_rate: Mapped[float] = mapped_column(Float, default=0.0)
    placement_count: Mapped[int] = mapped_column(Integer, default=0)
    relationship_score: Mapped[float] = mapped_column(Float, default=50.0)
    tags: Mapped[Optional[Any]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ContactEnrichment(Base):
    __tablename__ = "contact_enrichments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contact_id: Mapped[str] = mapped_column(String(36), index=True)
    source: Mapped[str] = mapped_column(String(50))
    raw_data: Mapped[Optional[Any]] = mapped_column(JSON)
    enriched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contact_id: Mapped[str] = mapped_column(String(36), index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(50), default="active")
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    next_followup_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_touches: Mapped[int] = mapped_column(Integer, default=0)
    last_response: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
