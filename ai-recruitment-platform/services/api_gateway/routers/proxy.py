"""
Generic reverse proxy router factory.
Forwards requests to upstream microservices, preserving headers, body, and query params.
"""

import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger("api-gateway.proxy")

# Headers that should NOT be forwarded upstream (hop-by-hop)
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

# Default timeouts
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
STREAMING_TIMEOUT = httpx.Timeout(None, connect=5.0)


def _filter_headers(headers: dict) -> dict:
    """Remove hop-by-hop headers before forwarding."""
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


def _map_upstream_error(status_code: int, service: str, detail: str) -> HTTPException:
    """Map upstream error responses to appropriate gateway errors."""
    if status_code == 401:
        return HTTPException(status_code=401, detail=f"Upstream auth error from {service}: {detail}")
    if status_code == 403:
        return HTTPException(status_code=403, detail=f"Upstream forbidden from {service}: {detail}")
    if status_code == 404:
        return HTTPException(status_code=404, detail=f"Resource not found in {service}")
    if status_code == 422:
        return HTTPException(status_code=422, detail=f"Validation error from {service}: {detail}")
    if status_code >= 500:
        return HTTPException(
            status_code=502,
            detail=f"Bad gateway — upstream service '{service}' returned {status_code}",
        )
    return HTTPException(status_code=status_code, detail=detail)


def create_proxy_router(
    service_name: str,
    upstream_url: str,
    prefix: str,
    circuit_breaker=None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
) -> APIRouter:
    """
    Factory function that creates an APIRouter with a catch-all proxy route.

    Args:
        service_name: Human-readable name for logging / error messages.
        upstream_url:  Base URL of the upstream service (e.g. http://employer-discovery:8001).
        prefix:        Path prefix handled by this router (e.g. /api/v1/employers).
        circuit_breaker: Optional CircuitBreaker instance.
        timeout:       httpx Timeout configuration.
    """
    router = APIRouter(prefix=prefix, tags=[service_name.replace("-", " ").title()])

    upstream_base = upstream_url.rstrip("/")
    strip_prefix = prefix

    async def _proxy(request: Request) -> Response:
        # Build the upstream path by stripping the gateway prefix
        upstream_path = request.url.path
        if upstream_path.startswith(strip_prefix):
            upstream_path = upstream_path[len(strip_prefix):]
        upstream_path = upstream_path or "/"

        # Build full URL
        query_string = request.url.query
        full_url = f"{upstream_base}{upstream_path}"
        if query_string:
            full_url = f"{full_url}?{query_string}"

        # Forward headers
        forward_headers = _filter_headers(dict(request.headers))

        # Inject user context headers from the auth middleware
        user = getattr(request.state, "user", None)
        if user:
            forward_headers["X-User-ID"] = user.user_id
            forward_headers["X-User-Email"] = user.email
            forward_headers["X-User-Role"] = user.role

        # Forward request ID
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            forward_headers["X-Request-ID"] = request_id

        # Read body
        body = await request.body()

        logger.debug(
            "Proxying %s %s -> %s",
            request.method,
            request.url.path,
            full_url,
        )

        async def _do_request():
            import httpx as _httpx

            async with _httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method=request.method,
                    url=full_url,
                    headers=forward_headers,
                    content=body,
                    follow_redirects=False,
                )
                return resp

        try:
            if circuit_breaker:
                upstream_response = await circuit_breaker.call(_do_request())
            else:
                upstream_response = await _do_request()
        except HTTPException:
            raise
        except httpx.ConnectTimeout:
            raise HTTPException(
                status_code=504,
                detail=f"Gateway timeout connecting to '{service_name}'",
            )
        except httpx.ReadTimeout:
            raise HTTPException(
                status_code=504,
                detail=f"Gateway timeout reading from '{service_name}'",
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Service '{service_name}' is unavailable",
            )
        except httpx.RequestError as exc:
            logger.error("Proxy request error for %s: %s", service_name, exc)
            raise HTTPException(
                status_code=502,
                detail=f"Bad gateway communicating with '{service_name}'",
            )

        # Map upstream errors
        if upstream_response.status_code >= 400:
            try:
                error_detail = upstream_response.json()
            except Exception:
                error_detail = upstream_response.text or str(upstream_response.status_code)

            if isinstance(error_detail, dict):
                detail_str = error_detail.get("detail", str(error_detail))
            else:
                detail_str = str(error_detail)

            raise _map_upstream_error(upstream_response.status_code, service_name, detail_str)

        # Stream back the response
        response_headers = _filter_headers(dict(upstream_response.headers))

        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type=upstream_response.headers.get("content-type"),
        )

    # Register catch-all routes for all HTTP methods
    for method in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
        router.add_api_route(
            "/{path:path}",
            _proxy,
            methods=[method],
            include_in_schema=False,
        )

    # Also register the root path
    for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
        router.add_api_route(
            "",
            _proxy,
            methods=[method],
            include_in_schema=False,
        )

    return router
