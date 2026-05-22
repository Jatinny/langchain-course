"""
Employer Discovery Service – FastAPI Application
Port 8001 | Discovers, classifies, and scores employers across Indian and global markets.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.employer_discovery.routers import discovery as discovery_router
from services.employer_discovery.routers import companies as companies_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application state container
# ---------------------------------------------------------------------------

class AppState:
    redis_client: aioredis.Redis | None = None
    kafka_consumer_task: asyncio.Task | None = None


app_state = AppState()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of infrastructure connections."""
    logger.info("Starting Employer Discovery Service on port 8001...")

    # Redis connection
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        app_state.redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=5,
        )
        await app_state.redis_client.ping()
        logger.info("Redis connected at %s", redis_url)
    except Exception as exc:
        logger.warning("Redis connection failed (non-fatal): %s", exc)
        app_state.redis_client = None

    # Store redis client in app state for DI
    app.state.redis = app_state.redis_client

    # Kafka consumer background task
    async def consume_kafka_events() -> None:
        """Background task to consume Kafka events for employer discovery."""
        from kafka import KafkaConsumer
        import json

        bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        topics = ["employer.qualified", "employer.discovered"]

        try:
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=bootstrap,
                group_id="employer-discovery-service",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                consumer_timeout_ms=1000,
            )
            logger.info("Kafka consumer started for topics: %s", topics)
            while True:
                records = consumer.poll(timeout_ms=1000, max_records=50)
                for tp, msgs in records.items():
                    for msg in msgs:
                        logger.debug(
                            "Kafka event: topic=%s payload=%s",
                            tp.topic,
                            str(msg.value)[:100],
                        )
                await asyncio.sleep(0.1)
        except Exception as exc:
            logger.warning("Kafka consumer error (non-fatal): %s", exc)

    try:
        app_state.kafka_consumer_task = asyncio.create_task(consume_kafka_events())
    except Exception as exc:
        logger.warning("Could not start Kafka consumer: %s", exc)

    yield

    # Shutdown
    logger.info("Shutting down Employer Discovery Service...")
    if app_state.kafka_consumer_task:
        app_state.kafka_consumer_task.cancel()
        try:
            await app_state.kafka_consumer_task
        except asyncio.CancelledError:
            pass

    if app_state.redis_client:
        await app_state.redis_client.aclose()

    logger.info("Employer Discovery Service shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Recruitment Platform – Employer Discovery Service",
    description=(
        "Discovers, classifies, and scores employers across Indian and global job markets. "
        "Uses LangGraph agents, job board scrapers, and ML classifiers."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log every incoming request with timing."""
    import time
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "%s %s %d %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Response-Time"] = f"{duration_ms}ms"
    return response


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Catch unhandled exceptions and return structured error responses."""
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(discovery_router.router, prefix="/discovery", tags=["Discovery"])
app.include_router(companies_router.router, prefix="/companies", tags=["Companies"])


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Basic liveness check."""
    return {"status": "healthy", "service": "employer-discovery", "port": 8001}


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check() -> dict:
    """Detailed health check including Redis and Kafka connectivity."""
    checks: dict = {
        "service": "employer-discovery",
        "status": "healthy",
        "checks": {},
    }

    # Redis
    try:
        if app_state.redis_client:
            await app_state.redis_client.ping()
            checks["checks"]["redis"] = "healthy"
        else:
            checks["checks"]["redis"] = "unavailable"
    except Exception as exc:
        checks["checks"]["redis"] = f"unhealthy: {exc}"
        checks["status"] = "degraded"

    # Kafka (lightweight check)
    try:
        from kafka.admin import KafkaAdminClient

        admin = KafkaAdminClient(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            request_timeout_ms=3000,
        )
        admin.close()
        checks["checks"]["kafka"] = "healthy"
    except Exception as exc:
        checks["checks"]["kafka"] = f"unavailable: {exc}"

    # PostgreSQL
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(
            os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/recruitment"),
            pool_pre_ping=True,
        )
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        await engine.dispose()
        checks["checks"]["postgresql"] = "healthy"
    except Exception as exc:
        checks["checks"]["postgresql"] = f"unavailable: {exc}"

    return checks


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Service root endpoint."""
    return {
        "service": "AI Recruitment Platform – Employer Discovery",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    uvicorn.run(
        "services.employer_discovery.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        reload=os.getenv("ENV", "production") == "development",
        log_level="info",
        workers=int(os.getenv("WORKERS", "1")),
    )
