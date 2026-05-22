"""
CRM Service — Port 8005
Manages employer pipelines, candidate submissions, placements, and commission tracking.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import Base
from routers import pipeline

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("crm_service")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/crm_db",
)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/2")
SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", "8005"))
ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
).split(",")

engine: AsyncEngine | None = None
async_session_factory: sessionmaker | None = None
redis_client: aioredis.Redis | None = None


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global engine, async_session_factory, redis_client  # noqa: PLW0603

    logger.info("CRM Service starting up …")

    engine = create_async_engine(
        DATABASE_URL,
        echo=bool(os.getenv("SQL_ECHO", False)),
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("CRM tables created / verified.")

    redis_client = await aioredis.from_url(
        REDIS_URL, encoding="utf-8", decode_responses=True
    )
    await redis_client.ping()
    logger.info("Redis connection established.")

    app.state.engine = engine
    app.state.async_session_factory = async_session_factory
    app.state.redis_client = redis_client

    logger.info("CRM Service ready on port %s.", SERVICE_PORT)
    yield

    logger.info("CRM Service shutting down …")
    if redis_client:
        await redis_client.aclose()
    if engine:
        await engine.dispose()
    logger.info("CRM Service shutdown complete.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Recruitment — CRM Service",
    description=(
        "Manages the full recruitment CRM: employer pipeline, candidate submissions, "
        "placement tracking, commission calculation, and activity logging."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(pipeline.router, prefix="/api/v1", tags=["crm", "pipeline"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "crm-service", "port": SERVICE_PORT})


@app.get("/ready", tags=["ops"])
async def readiness_check() -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ready" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )


@app.get("/", tags=["ops"])
async def root() -> JSONResponse:
    return JSONResponse({"service": "crm-service", "version": "1.0.0", "docs": "/docs"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=bool(os.getenv("RELOAD", False)),
        log_level="info",
    )
