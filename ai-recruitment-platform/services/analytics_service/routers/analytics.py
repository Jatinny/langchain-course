"""Analytics endpoints — dashboard, revenue, outreach, market intelligence."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from common.database import get_async_db
from common.config import settings
from common.llm import generate_text
from common.logging import get_logger
from services.analytics_service.schemas import (
    DashboardResponse, KPIData, OutreachPerformance, RevenueDataPoint,
    TemplatePerformance, AIRecommendationResponse, SalaryIntelligenceResponse,
    MarketDemandResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = get_logger(__name__)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_async_db),
) -> DashboardResponse:
    """Main dashboard with all KPIs."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # KPIs - query across services (simplified with direct SQL)
    try:
        employers_row = (await db.execute(text("SELECT COUNT(*) total FROM employers WHERE status='active'"))).fetchone()
        campaigns_row = (await db.execute(text("SELECT COUNT(*) total FROM outreach_campaigns WHERE status='active'"))).fetchone()
        placements_row = (await db.execute(text(
            "SELECT COUNT(*) cnt, COALESCE(SUM(commission_amount),0) rev FROM placements WHERE start_date >= :ms"
        ), {"ms": month_start})).fetchone()
        pipeline_row = (await db.execute(text(
            "SELECT COALESCE(SUM(expected_monthly_revenue * probability / 100.0), 0) val FROM employer_pipeline WHERE stage NOT IN ('closed_won','closed_lost')"
        ))).fetchone()
    except Exception:
        employers_row = placements_row = pipeline_row = campaigns_row = None

    kpis = KPIData(
        total_employers=employers_row.total if employers_row else 0,
        active_campaigns=campaigns_row.total if campaigns_row else 0,
        placements_mtd=placements_row.cnt if placements_row else 0,
        revenue_mtd=float(placements_row.rev) if placements_row else 0.0,
        pipeline_value=float(pipeline_row.val) if pipeline_row else 0.0,
    )

    # Revenue trend (last 6 months)
    revenue_trend = []
    for i in range(5, -1, -1):
        month_dt = now - timedelta(days=30 * i)
        try:
            rev = (await db.execute(text(
                "SELECT COALESCE(SUM(commission_amount),0) rev, COUNT(*) cnt FROM placements "
                "WHERE EXTRACT(MONTH FROM start_date)=:m AND EXTRACT(YEAR FROM start_date)=:y"
            ), {"m": month_dt.month, "y": month_dt.year})).fetchone()
            revenue_trend.append(RevenueDataPoint(
                month=month_dt.strftime("%b"), year=month_dt.year,
                revenue=float(rev.rev) if rev else 0.0,
                placements=rev.cnt if rev else 0,
                commissions=float(rev.rev) if rev else 0.0,
            ))
        except Exception:
            revenue_trend.append(RevenueDataPoint(
                month=month_dt.strftime("%b"), year=month_dt.year,
                revenue=0.0, placements=0, commissions=0.0,
            ))

    # Outreach performance
    try:
        orow = (await db.execute(text("""
            SELECT SUM(sent) sent, SUM(delivered) delivered, SUM(opened) opened,
                   SUM(replied) replied, SUM(converted) converted
            FROM outreach_analytics WHERE date >= :ms
        """), {"ms": month_start})).fetchone()
        sent = orow.sent or 0
        opened = orow.opened or 0
        replied = orow.replied or 0
        outreach = OutreachPerformance(
            sent=sent, delivered=orow.delivered or 0, opened=opened, replied=replied,
            converted=orow.converted or 0,
            open_rate=opened / sent if sent > 0 else 0.0,
            reply_rate=replied / sent if sent > 0 else 0.0,
            conversion_rate=(orow.converted or 0) / sent if sent > 0 else 0.0,
        )
    except Exception:
        outreach = OutreachPerformance()

    # AI recommendations
    try:
        recs = (await db.execute(text(
            "SELECT id, type, title, description, priority, data, created_at FROM ai_recommendations "
            "WHERE acted_upon=false ORDER BY created_at DESC LIMIT 5"
        ))).fetchall()
        recommendations = [AIRecommendationResponse(
            id=str(r.id), type=r.type, title=r.title,
            description=r.description, priority=r.priority, created_at=r.created_at
        ) for r in recs]
    except Exception:
        recommendations = []

    return DashboardResponse(
        kpis=kpis,
        revenue_trend=revenue_trend,
        outreach_performance=outreach,
        top_templates=[],
        ai_recommendations=recommendations,
    )


@router.get("/salary-intelligence", response_model=SalaryIntelligenceResponse)
async def get_salary_intelligence(
    role: str = Query("Java Developer"),
    location: str = Query("Bangalore"),
    yoe_min: int = Query(0),
    yoe_max: int = Query(15),
) -> SalaryIntelligenceResponse:
    """Get salary benchmarks for a role and location."""
    import json
    try:
        with open("/app/data/salary_benchmarks_india.json") as f:
            data = json.load(f)
        yoe_range = f"{yoe_min}-{yoe_max}"
        role_data = data.get("roles", {}).get(role, {})
        for yoe_key, yoe_val in role_data.items():
            start, end = map(int, yoe_key.split("-")) if "-" in yoe_key else (int(yoe_key.replace("+", "")), 99)
            if yoe_min >= start:
                cities = yoe_val.get("cities", {})
                city_data = cities.get(location, yoe_val)
                return SalaryIntelligenceResponse(
                    role=role, location=location, yoe_range=yoe_range,
                    min=city_data.get("min", yoe_val.get("min", 0)),
                    median=city_data.get("median", yoe_val.get("median", 0)),
                    max=city_data.get("max", yoe_val.get("max", 0)),
                    source_count=50,
                )
    except Exception:
        pass
    return SalaryIntelligenceResponse(role=role, location=location, yoe_range=f"{yoe_min}-{yoe_max}", min=0, median=0, max=0, source_count=0)


@router.get("/market-demand")
async def get_market_demand(
    role: str = Query("Java Developer"),
    region: str = Query("India"),
) -> MarketDemandResponse:
    """Get market demand trends for a role."""
    high_demand_roles = ["AI Engineer", "Cloud Engineer", "DevOps Engineer", "Data Engineer"]
    demand = "very_high" if role in high_demand_roles else "high"
    return MarketDemandResponse(
        role=role, region=region, demand_level=demand, trend="increasing",
        top_hiring_companies=["TCS", "Infosys", "Wipro", "HCL", "Accenture"],
        top_skills=["Python", "AWS", "Docker", "Kubernetes"] if "Engineer" in role else ["Java", "Spring Boot", "SQL"],
        avg_salary=1800000 if region == "India" else 120000,
    )


@router.post("/report")
async def generate_ai_report(
    period: str = Query("weekly"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Generate AI-powered recruitment performance report."""
    report_id = str(uuid.uuid4())

    async def create_report():
        prompt = f"""
Generate a {period} recruitment performance report for a staffing agency in India.
Include: top performing outreach templates, employer pipeline health, candidate submission rates,
revenue forecast, and 3 actionable recommendations to improve performance.
Format as a structured report.
"""
        try:
            report_text = await generate_text(prompt, temperature=0.3)
            logger.info("AI report generated", report_id=report_id)
        except Exception as e:
            logger.error("Report generation failed", error=str(e))

    if background_tasks:
        background_tasks.add_task(create_report)

    return {"report_id": report_id, "status": "generating", "period": period}


@router.get("/recommendations")
async def get_recommendations(
    limit: int = Query(10),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    try:
        rows = (await db.execute(text(
            "SELECT * FROM ai_recommendations WHERE acted_upon=false ORDER BY priority, created_at DESC LIMIT :limit"
        ), {"limit": limit})).fetchall()
        return {"recommendations": [dict(r._mapping) for r in rows]}
    except Exception:
        return {"recommendations": []}
