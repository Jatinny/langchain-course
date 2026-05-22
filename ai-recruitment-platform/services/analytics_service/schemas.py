from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class KPIData(BaseModel):
    total_employers: int = 0
    active_campaigns: int = 0
    placements_mtd: int = 0
    revenue_mtd: float = 0.0
    pipeline_value: float = 0.0
    outreach_reply_rate: float = 0.0
    avg_time_to_placement_days: float = 0.0


class OutreachPerformance(BaseModel):
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    replied: int = 0
    converted: int = 0
    open_rate: float = 0.0
    reply_rate: float = 0.0
    conversion_rate: float = 0.0


class RevenueDataPoint(BaseModel):
    month: str
    year: int
    revenue: float
    placements: int
    commissions: float


class TemplatePerformance(BaseModel):
    id: str
    name: str
    channel: str
    sent_count: int
    reply_rate: float
    conversion_rate: float


class AIRecommendationResponse(BaseModel):
    id: str
    type: str
    title: str
    description: str
    priority: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    kpis: KPIData
    revenue_trend: List[RevenueDataPoint]
    outreach_performance: OutreachPerformance
    top_templates: List[TemplatePerformance]
    ai_recommendations: List[AIRecommendationResponse]


class SalaryIntelligenceResponse(BaseModel):
    role: str
    location: str
    yoe_range: str
    min: int
    median: int
    max: int
    currency: str = "INR"
    source_count: int


class MarketDemandResponse(BaseModel):
    role: str
    region: str
    demand_level: str
    trend: str
    top_hiring_companies: List[str]
    top_skills: List[str]
    avg_salary: int
