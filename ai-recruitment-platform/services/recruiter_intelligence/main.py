"""Recruiter Intelligence Service — contact enrichment and management."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.config import settings
from common.database import init_db, close_db
from common.logging import configure_logging, get_logger
from common.observability import MetricsMiddleware, init_sentry, get_metrics_response
from services.recruiter_intelligence.routers.contacts import router as contacts_router

configure_logging("recruiter-intelligence", settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Recruiter Intelligence Service starting")
    await init_db()
    init_sentry("recruiter-intelligence")
    yield
    await close_db()
    logger.info("Recruiter Intelligence Service stopped")


app = FastAPI(
    title="Recruiter Intelligence Service",
    description="Contact enrichment via Apollo, Hunter.io, LinkedIn",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware, service_name="recruiter-intelligence")

app.include_router(contacts_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "recruiter-intelligence"}


@app.get("/metrics")
async def metrics():
    from fastapi.responses import Response
    data, content_type = get_metrics_response()
    return Response(content=data, media_type=content_type)
