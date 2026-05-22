"""Pydantic schemas for recruiter intelligence service."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr


class RecruiterContactBase(BaseModel):
    name: str
    title: Optional[str] = None
    company: Optional[str] = None
    company_id: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None


class RecruiterContactCreate(RecruiterContactBase):
    pass


class RecruiterContactUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class RecruiterContactResponse(RecruiterContactBase):
    id: str
    verified_email: bool = False
    verification_source: Optional[str] = None
    last_contacted: Optional[datetime] = None
    response_rate: float = 0.0
    placement_count: int = 0
    relationship_score: float = 50.0
    created_at: datetime

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    items: List[RecruiterContactResponse]
    total: int
    page: int
    limit: int


class EnrichmentResult(BaseModel):
    contact_id: str
    email: Optional[str] = None
    verified: bool = False
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    enrichment_source: str
    confidence: float = 0.0
    raw_data: Optional[Dict[str, Any]] = None


class OutreachSequenceResponse(BaseModel):
    id: str
    contact_id: str
    status: str
    current_step: int
    next_followup_date: Optional[datetime] = None
    total_touches: int

    class Config:
        from_attributes = True


class ContactStatsResponse(BaseModel):
    total_contacts: int
    verified_emails: int
    avg_response_rate: float
    total_placements: int
    avg_relationship_score: float
    by_company: Dict[str, int]
