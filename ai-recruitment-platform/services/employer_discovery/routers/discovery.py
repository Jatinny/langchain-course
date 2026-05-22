"""Employer discovery trigger and status endpoints."""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_async_db
from common.kafka_client import KafkaProducerClient
from common.config import settings
from common.logging import get_logger
from services.employer_discovery.schemas import (
    DiscoveryRequest,
    DiscoveryJobResponse,
    DiscoveryResultResponse,
    EmployerResponse,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])
logger = get_logger(__name__)

# In-memory job store (use Redis in production)
_discovery_jobs: dict = {}


async def run_discovery_job(job_id: str, request: DiscoveryRequest) -> None:
    """Background task that runs the discovery agent."""
    from agents.employer_discovery_agent import EmployerDiscoveryAgent

    _discovery_jobs[job_id]["status"] = "running"

    try:
        agent = EmployerDiscoveryAgent()
        result = await agent.run({
            "regions": [r.value for r in request.regions],
            "industries": [i.value for i in request.industries],
            "roles": request.roles,
            "limit": request.limit,
            "vendor_friendly_only": request.vendor_friendly_only,
            "job_id": job_id,
        })

        employers = result.get("employers", [])
        _discovery_jobs[job_id].update({
            "status": "completed",
            "employers_found": len(employers),
            "employers": employers,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        # Publish to Kafka
        producer = KafkaProducerClient.get_instance()
        for employer in employers:
            producer.publish(
                topic=settings.topic_employer_discovered,
                message={**employer, "job_id": job_id},
                key=employer.get("id", str(uuid.uuid4())),
            )

        logger.info("Discovery job completed", job_id=job_id, found=len(employers))
    except Exception as e:
        logger.error("Discovery job failed", job_id=job_id, error=str(e))
        _discovery_jobs[job_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


@router.post("/start", response_model=DiscoveryJobResponse, status_code=202)
async def start_discovery(
    request: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
) -> DiscoveryJobResponse:
    """Trigger AI employer discovery job."""
    job_id = str(uuid.uuid4())
    estimated_time = len(request.regions) * len(request.industries) * 20

    _discovery_jobs[job_id] = {
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": request.model_dump(),
        "employers_found": 0,
        "employers": [],
    }

    background_tasks.add_task(run_discovery_job, job_id, request)

    logger.info("Discovery job queued", job_id=job_id, regions=request.regions, industries=request.industries)
    return DiscoveryJobResponse(
        job_id=job_id,
        status="queued",
        estimated_time_seconds=estimated_time,
        regions=[r.value for r in request.regions],
        industries=[i.value for i in request.industries],
        roles=request.roles,
    )


@router.get("/status/{job_id}")
async def get_discovery_status(job_id: str) -> dict:
    """Get the current status of a discovery job."""
    if job_id not in _discovery_jobs:
        raise HTTPException(status_code=404, detail=f"Discovery job {job_id} not found")
    job = _discovery_jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "employers_found": job.get("employers_found", 0),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "error": job.get("error"),
    }


@router.get("/results/{job_id}", response_model=DiscoveryResultResponse)
async def get_discovery_results(job_id: str) -> DiscoveryResultResponse:
    """Get full results of a completed discovery job."""
    if job_id not in _discovery_jobs:
        raise HTTPException(status_code=404, detail=f"Discovery job {job_id} not found")
    job = _discovery_jobs[job_id]
    if job["status"] not in ("completed", "failed"):
        raise HTTPException(status_code=202, detail=f"Job is still {job['status']}")

    return DiscoveryResultResponse(
        job_id=job_id,
        status=job["status"],
        employers_found=job.get("employers_found", 0),
        employers=job.get("employers", []),
        completed_at=job.get("completed_at"),
    )


@router.post("/qualify")
async def qualify_employers(
    employer_ids: list[str],
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger AI qualification scoring for a batch of employers."""
    from agents.lead_qualification_agent import LeadQualificationAgent

    async def qualify_batch():
        agent = LeadQualificationAgent()
        for emp_id in employer_ids:
            await agent.run({"employer_id": emp_id})

    background_tasks.add_task(qualify_batch)
    return {"message": f"Qualifying {len(employer_ids)} employers", "status": "queued"}


@router.get("/trending")
async def get_trending_companies(
    region: str = Query("India"),
    industry: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Get companies with trending hiring activity."""
    from sqlalchemy import text
    query = """
        SELECT id, name, industry, region, score, hiring_volume, is_vendor_friendly
        FROM employers
        WHERE region = :region
          AND status = 'active'
          AND hiring_volume > 0
          {}
        ORDER BY hiring_volume DESC, score DESC
        LIMIT :limit
    """.format("AND industry = :industry" if industry else "")

    params = {"region": region, "limit": limit}
    if industry:
        params["industry"] = industry

    result = await db.execute(text(query), params)
    rows = result.fetchall()
    return {
        "region": region,
        "industry": industry,
        "companies": [
            {
                "id": str(r.id), "name": r.name, "industry": r.industry,
                "region": r.region, "score": r.score,
                "hiring_volume": r.hiring_volume,
                "is_vendor_friendly": r.is_vendor_friendly,
            }
            for r in rows
        ],
    }
