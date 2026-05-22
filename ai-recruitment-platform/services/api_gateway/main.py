"""
API Gateway - Main entry point for the AI Recruitment Platform.
Handles routing, authentication, rate limiting, circuit breaking, and observability.
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from middleware.auth import JWTAuthMiddleware, get_current_user
from middleware.rate_limiter import RateLimiterMiddleware
from routers.proxy import create_proxy_router

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("api-gateway")

# ── Prometheus metrics ────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total requests processed by the gateway",
    ["method", "path", "status_code", "service"],
)
REQUEST_LATENCY = Histogram(
    "gateway_request_duration_seconds",
    "Request latency in seconds",
    ["method", "path", "service"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
CIRCUIT_BREAKER_STATE = Counter(
    "gateway_circuit_breaker_trips_total",
    "Circuit breaker trips",
    ["service"],
)

# ── Circuit Breaker ────────────────────────────────────────────────────────────
class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        service: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
    ):
        self.service = service
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, coro):
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info(f"Circuit breaker for {self.service} moved to HALF_OPEN")
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service {self.service} is temporarily unavailable (circuit open)",
                    )

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service {self.service} is recovering (circuit half-open)",
                    )
                self.half_open_calls += 1

        try:
            result = await coro
            async with self._lock:
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit breaker for {self.service} CLOSED (recovery successful)")
            return result
        except Exception as exc:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if (
                    self.failure_count >= self.failure_threshold
                    or self.state == CircuitBreakerState.HALF_OPEN
                ):
                    if self.state != CircuitBreakerState.OPEN:
                        self.state = CircuitBreakerState.OPEN
                        CIRCUIT_BREAKER_STATE.labels(service=self.service).inc()
                        logger.error(
                            f"Circuit breaker for {self.service} OPENED after {self.failure_count} failures"
                        )
            raise exc


# ── Service Registry ──────────────────────────────────────────────────────────
SERVICE_REGISTRY: dict[str, str] = {
    "employers":  "http://employer-discovery:8001",
    "recruiters": "http://recruiter-intelligence:8002",
    "outreach":   "http://outreach-engine:8003",
    "candidates": "http://candidate-matching:8004",
    "crm":        "http://crm-service:8005",
    "analytics":  "http://analytics-service:8006",
}

circuit_breakers: dict[str, CircuitBreaker] = {
    name: CircuitBreaker(service=name) for name in SERVICE_REGISTRY
}

# ── HTTP Client Pool ──────────────────────────────────────────────────────────
http_client: Optional[httpx.AsyncClient] = None
redis_client: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, redis_client
    import os

    # Initialize HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        follow_redirects=False,
    )

    # Initialize Redis client
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_client = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    logger.info("API Gateway started — HTTP client and Redis initialized")
    yield

    await http_client.aclose()
    await redis_client.aclose()
    logger.info("API Gateway shutdown — connections closed")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Recruitment Platform — API Gateway",
    description=(
        "Central API Gateway providing authentication, rate limiting, "
        "circuit breaking, and reverse proxy to all platform microservices."
    ),
    version="1.0.0",
    docs_url=None,   # custom below
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8080,https://app.recruitai.io",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(JWTAuthMiddleware)
app.add_middleware(RateLimiterMiddleware)


# ── Request ID + Logging middleware ───────────────────────────────────────────
@app.middleware("http")
async def request_instrumentation(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.start_time = time.time()

    logger.info(
        "Incoming request | id=%s method=%s path=%s client=%s",
        request_id,
        request.method,
        request.url.path,
        request.client.host if request.client else "unknown",
    )

    response: Response = await call_next(request)
    duration = time.time() - request.state.start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.4f}s"

    # Determine service name from path
    path_parts = request.url.path.strip("/").split("/")
    service = path_parts[2] if len(path_parts) >= 3 else "unknown"

    REQUEST_COUNT.labels(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        service=service,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        path=request.url.path,
        service=service,
    ).observe(duration)

    logger.info(
        "Request complete | id=%s status=%d duration=%.3fs",
        request_id,
        response.status_code,
        duration,
    )
    return response


# ── Health check aggregation ──────────────────────────────────────────────────
@app.get("/health", tags=["Health"], include_in_schema=False)
async def gateway_health():
    return {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": time.time(),
    }


@app.get("/api/v1/health", tags=["Health"])
async def aggregated_health():
    """Aggregates health status from all downstream services."""
    results: dict[str, dict] = {}
    timeout = httpx.Timeout(5.0)

    async def check_service(name: str, base_url: str):
        try:
            cb = circuit_breakers[name]
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await cb.call(client.get(f"{base_url}/health"))
            results[name] = {"status": "healthy", "http_status": resp.status_code}
        except HTTPException as exc:
            results[name] = {"status": "circuit_open", "detail": exc.detail}
        except Exception as exc:
            results[name] = {"status": "unhealthy", "error": str(exc)}

    await asyncio.gather(
        *[check_service(name, url) for name, url in SERVICE_REGISTRY.items()]
    )

    overall = "healthy" if all(r["status"] == "healthy" for r in results.values()) else "degraded"
    return {
        "status": overall,
        "gateway": "healthy",
        "services": results,
        "timestamp": time.time(),
    }


# ── Metrics endpoint ──────────────────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Custom OpenAPI docs ───────────────────────────────────────────────────────
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title="AI Recruitment Platform API",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


# ── Proxy routes ──────────────────────────────────────────────────────────────
PROXY_ROUTES = [
    ("employers",  "/api/v1/employers"),
    ("recruiters", "/api/v1/recruiters"),
    ("outreach",   "/api/v1/outreach"),
    ("candidates", "/api/v1/candidates"),
    ("crm",        "/api/v1/crm"),
    ("analytics",  "/api/v1/analytics"),
]

for service_name, prefix in PROXY_ROUTES:
    router = create_proxy_router(
        service_name=service_name,
        upstream_url=SERVICE_REGISTRY[service_name],
        prefix=prefix,
        circuit_breaker=circuit_breakers[service_name],
    )
    app.include_router(router)


# ── Token refresh (public endpoint) ──────────────────────────────────────────
from middleware.auth import refresh_token_endpoint  # noqa: E402

app.include_router(refresh_token_endpoint, prefix="/api/v1/auth", tags=["Auth"])


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception for request %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        loop="uvloop",
        http="httptools",
        log_level="info",
        access_log=False,  # handled by middleware
    )
