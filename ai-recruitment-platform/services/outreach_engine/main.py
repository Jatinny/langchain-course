"""
Outreach Engine Service - Port 8003
Handles AI-powered outreach automation for email, LinkedIn, and WhatsApp.
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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import Base
from routers import campaigns

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("outreach_engine")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/outreach_db",
)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", "8003"))
ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
).split(",")

# ---------------------------------------------------------------------------
# Global state containers (populated during lifespan)
# ---------------------------------------------------------------------------
engine: AsyncEngine | None = None
async_session_factory: sessionmaker | None = None
redis_client: aioredis.Redis | None = None


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown logic."""
    global engine, async_session_factory, redis_client

    logger.info("Outreach Engine starting up …")

    # Database
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
    logger.info("Database tables created / verified.")

    # Redis
    redis_client = await aioredis.from_url(
        REDIS_URL, encoding="utf-8", decode_responses=True
    )
    await redis_client.ping()
    logger.info("Redis connection established.")

    # Attach to app state so routers can access them
    app.state.engine = engine
    app.state.async_session_factory = async_session_factory
    app.state.redis_client = redis_client

    logger.info("Outreach Engine ready on port %s.", SERVICE_PORT)
    yield

    # Shutdown
    logger.info("Outreach Engine shutting down …")
    if redis_client:
        await redis_client.aclose()
    if engine:
        await engine.dispose()
    logger.info("Outreach Engine shutdown complete.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Recruitment — Outreach Engine",
    description=(
        "Automates multi-channel outreach (email, LinkedIn, WhatsApp) "
        "with AI-generated, personalised messages for recruitment sourcing."
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
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Tighten in production
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns", "outreach"])


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health_check() -> JSONResponse:
    """Liveness probe — always returns 200 if process is alive."""
    return JSONResponse({"status": "ok", "service": "outreach-engine", "port": SERVICE_PORT})


@app.get("/ready", tags=["ops"])
async def readiness_check() -> JSONResponse:
    """Readiness probe — verifies DB and Redis connectivity."""
    checks: dict[str, str] = {}

    # DB
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Redis
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse({"status": "ready" if all_ok else "degraded", "checks": checks}, status_code=status_code)


@app.get("/", tags=["ops"])
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "outreach-engine",
            "version": "1.0.0",
            "docs": "/docs",
        }
    )


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
