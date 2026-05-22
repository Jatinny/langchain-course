"""Observability: Prometheus metrics, Sentry tracing, health checks."""
import time
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict

import sentry_sdk
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)
from prometheus_client.registry import CollectorRegistry
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from common.config import settings

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["service", "method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Active HTTP requests",
    ["service"],
)
KAFKA_MESSAGES_PUBLISHED = Counter(
    "kafka_messages_published_total",
    "Kafka messages published",
    ["service", "topic"],
)
KAFKA_MESSAGES_CONSUMED = Counter(
    "kafka_messages_consumed_total",
    "Kafka messages consumed",
    ["service", "topic"],
)
AI_REQUESTS = Counter(
    "ai_requests_total",
    "AI LLM requests",
    ["service", "model", "operation"],
)
AI_TOKENS_USED = Counter(
    "ai_tokens_used_total",
    "AI tokens consumed",
    ["service", "model"],
)
EMPLOYER_DISCOVERY_TOTAL = Counter(
    "employer_discovery_total",
    "Employers discovered",
    ["source", "region", "industry"],
)
OUTREACH_SENT = Counter(
    "outreach_sent_total",
    "Outreach messages sent",
    ["channel", "campaign"],
)
PLACEMENTS_MADE = Counter(
    "placements_made_total",
    "Successful placements",
    ["industry", "region"],
)
REVENUE_EARNED = Counter(
    "revenue_earned_total",
    "Revenue earned in USD",
    ["placement_type"],
)


def init_sentry(service_name: str) -> None:
    """Initialize Sentry error tracking."""
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"{service_name}@{settings.app_version}",
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        server_name=service_name,
    )
    logger.info("Sentry initialized", service=service_name)


class MetricsMiddleware:
    """ASGI middleware for Prometheus metrics collection."""

    def __init__(self, app, service_name: str) -> None:
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "unknown")
        method = scope.get("method", "unknown")

        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        ACTIVE_REQUESTS.labels(service=self.service_name).inc()

        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            ACTIVE_REQUESTS.labels(service=self.service_name).dec()
            REQUEST_COUNT.labels(
                service=self.service_name,
                method=method,
                endpoint=path,
                status_code=status_code,
            ).inc()
            REQUEST_LATENCY.labels(
                service=self.service_name,
                method=method,
                endpoint=path,
            ).observe(duration)


def get_metrics_response() -> tuple[bytes, str]:
    """Get Prometheus metrics in text format."""
    return generate_latest(), CONTENT_TYPE_LATEST


async def health_check_response(service_name: str, checks: Dict[str, Callable]) -> Dict[str, Any]:
    """Run health checks and return status."""
    results: Dict[str, Any] = {
        "service": service_name,
        "status": "healthy",
        "checks": {},
    }

    for check_name, check_fn in checks.items():
        try:
            if callable(check_fn):
                import asyncio
                if asyncio.iscoroutinefunction(check_fn):
                    await check_fn()
                else:
                    check_fn()
            results["checks"][check_name] = "ok"
        except Exception as e:
            results["checks"][check_name] = f"error: {e}"
            results["status"] = "degraded"

    return results
