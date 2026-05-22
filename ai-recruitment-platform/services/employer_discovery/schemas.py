"""Pydantic schemas for employer discovery service."""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator


class IndustryEnum(str, Enum):
    IT_SERVICES = "IT Services"
    BFSI = "BFSI"
    PRODUCT = "Product"
    STARTUP = "Startup"
    GCC = "GCC"
    HEALTHCARE_IT = "Healthcare IT"
    EDTECH = "EdTech"
    FINTECH = "FinTech"
    ECOMMERCE = "E-commerce"
    TELECOM = "Telecom"
    AI_ML = "AI/ML"
    CONSULTING = "Consulting"
    MANUFACTURING = "Manufacturing"
    OTHER = "Other"


class CompanySizeEnum(str, Enum):
    MICRO = "1-10"
    SMALL = "11-50"
    MEDIUM = "51-200"
    LARGE = "201-1000"
    ENTERPRISE = "1001-5000"
    GIANT = "5001+"


class RegionEnum(str, Enum):
    INDIA = "India"
    USA = "USA"
    CANADA = "Canada"
    UK = "UK"
    EUROPE = "Europe"
    SINGAPORE = "Singapore"
    AUSTRALIA = "Australia"
    UAE = "UAE"


class EmployerStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"
    PENDING = "pending"


class ScoreBreakdown(BaseModel):
    vendor_friendliness: float = 0.0
    hiring_frequency: float = 0.0
    recruiter_responsiveness: float = 0.0
    remote_flexibility: float = 0.0
    salary_competitiveness: float = 0.0
    contract_opportunities: float = 0.0
    placement_success: float = 0.0
    overall: float = 0.0


class HiringContactBase(BaseModel):
    name: str
    title: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class HiringContactCreate(HiringContactBase):
    employer_id: UUID


class HiringContactResponse(HiringContactBase):
    id: UUID
    employer_id: UUID
    verified: bool = False
    last_contacted: Optional[datetime] = None
    response_rate: float = 0.0

    class Config:
        from_attributes = True


class JobPostingBase(BaseModel):
    title: str
    description: Optional[str] = None
    skills_required: List[str] = []
    location: Optional[str] = None
    job_type: str = "permanent"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    source_platform: Optional[str] = None
    source_url: Optional[str] = None


class JobPostingCreate(JobPostingBase):
    employer_id: UUID


class JobPostingResponse(JobPostingBase):
    id: UUID
    employer_id: UUID
    posted_date: Optional[datetime] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class EmployerBase(BaseModel):
    name: str
    industry: Optional[IndustryEnum] = None
    size: Optional[CompanySizeEnum] = None
    country: Optional[str] = None
    region: Optional[RegionEnum] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_vendor_friendly: bool = False
    accepts_contract: bool = False
    accepts_c2h: bool = False
    hiring_volume: int = 0


class EmployerCreate(EmployerBase):
    pass


class EmployerUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[IndustryEnum] = None
    size: Optional[CompanySizeEnum] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_vendor_friendly: Optional[bool] = None
    accepts_contract: Optional[bool] = None
    accepts_c2h: Optional[bool] = None
    hiring_volume: Optional[int] = None
    status: Optional[EmployerStatusEnum] = None


class EmployerResponse(EmployerBase):
    id: UUID
    score: float = 0.0
    score_breakdown: Optional[ScoreBreakdown] = None
    status: EmployerStatusEnum = EmployerStatusEnum.ACTIVE
    contacts_count: int = 0
    active_jobs_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployerListResponse(BaseModel):
    items: List[EmployerResponse]
    total: int
    page: int
    limit: int
    pages: int


class DiscoveryRequest(BaseModel):
    regions: List[RegionEnum] = [RegionEnum.INDIA]
    industries: List[IndustryEnum] = [IndustryEnum.IT_SERVICES]
    roles: List[str] = ["Java Developer"]
    limit: int = 100
    vendor_friendly_only: bool = False
    include_gccs: bool = True
    include_startups: bool = True

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        return min(max(v, 1), 500)


class DiscoveryJobResponse(BaseModel):
    job_id: str
    status: str
    estimated_time_seconds: int
    regions: List[str]
    industries: List[str]
    roles: List[str]


class DiscoveryResultResponse(BaseModel):
    job_id: str
    status: str
    employers_found: int
    employers: List[EmployerResponse]
    completed_at: Optional[datetime] = None


class EmployerStatsResponse(BaseModel):
    total_employers: int
    vendor_friendly: int
    contract_accepting: int
    by_industry: dict
    by_region: dict
    avg_score: float
    high_score_count: int
