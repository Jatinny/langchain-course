"""Analytics Service — metrics, dashboards, AI recommendations."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from common.config import settings
from common.database import init_db, close_db
from common.logging import configure_logging, get_logger
from common.observability import MetricsMiddleware, init_sentry, get_metrics_response
from services.analytics_service.routers.analytics import router as analytics_router

configure_logging("analytics-service", settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Analytics Service starting")
    await init_db()
    init_sentry("analytics-service")
    yield
    await close_db()
    logger.info("Analytics Service stopped")


app = FastAPI(
    title="Analytics Service",
    description="Platform analytics, revenue tracking, AI recommendations",
    version=settings.app_version,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(MetricsMiddleware, service_name="analytics-service")
app.include_router(analytics_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "analytics-service"}


@app.get("/metrics")
async def metrics():
    from fastapi.responses import Response
    data, ct = get_metrics_response()
    return Response(content=data, media_type=ct)
