"""
JWT Authentication Middleware with RS256, RBAC, and token refresh support.
"""

import os
import logging
import time
from typing import Optional, Set
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWKClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("api-gateway.auth")

# ── Configuration ─────────────────────────────────────────────────────────────
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "RS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
JWT_ISSUER = os.getenv("JWT_ISSUER", "ai-recruitment-platform")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "api-gateway")

# For RS256 we need the public key for verification and private key for signing
_PRIVATE_KEY_PATH = os.getenv("JWT_PRIVATE_KEY_PATH", "/run/secrets/jwt_private_key")
_PUBLIC_KEY_PATH = os.getenv("JWT_PUBLIC_KEY_PATH", "/run/secrets/jwt_public_key")
_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")  # fallback for HS256 in dev


def _load_key(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


_PRIVATE_KEY_BYTES = _load_key(_PRIVATE_KEY_PATH)
_PUBLIC_KEY_BYTES = _load_key(_PUBLIC_KEY_PATH)


def _get_decode_key():
    if JWT_ALGORITHM == "RS256" and _PUBLIC_KEY_BYTES:
        return serialization.load_pem_public_key(_PUBLIC_KEY_BYTES, backend=default_backend())
    # Fallback: HS256 with secret key (dev/testing only)
    return _JWT_SECRET_KEY


def _get_encode_key():
    if JWT_ALGORITHM == "RS256" and _PRIVATE_KEY_BYTES:
        return serialization.load_pem_private_key(
            _PRIVATE_KEY_BYTES, password=None, backend=default_backend()
        )
    return _JWT_SECRET_KEY


# ── RBAC ──────────────────────────────────────────────────────────────────────
ROLES = {"admin", "recruiter", "viewer"}

ROLE_PERMISSIONS: dict[str, Set[str]] = {
    "admin": {
        "employers:read", "employers:write", "employers:delete",
        "recruiters:read", "recruiters:write", "recruiters:delete",
        "outreach:read", "outreach:write", "outreach:delete",
        "candidates:read", "candidates:write", "candidates:delete",
        "crm:read", "crm:write", "crm:delete",
        "analytics:read", "analytics:write",
        "users:read", "users:write",
    },
    "recruiter": {
        "employers:read", "employers:write",
        "recruiters:read",
        "outreach:read", "outreach:write",
        "candidates:read", "candidates:write",
        "crm:read", "crm:write",
        "analytics:read",
    },
    "viewer": {
        "employers:read",
        "recruiters:read",
        "candidates:read",
        "crm:read",
        "analytics:read",
    },
}

# ── Public routes (no auth required) ─────────────────────────────────────────
PUBLIC_PATHS: Set[str] = {
    "/health",
    "/metrics",
    "/docs",
    "/api/v1/openapi.json",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
}

PUBLIC_PATH_PREFIXES: Set[str] = {
    "/static/",
}


# ── Token models ──────────────────────────────────────────────────────────────
class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    full_name: str
    permissions: Set[str]
    jti: str  # JWT ID for revocation


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Token creation ─────────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    import uuid

    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    encode_key = _get_encode_key()
    algo = JWT_ALGORITHM if (JWT_ALGORITHM == "RS256" and _PRIVATE_KEY_BYTES) else "HS256"
    return jwt.encode(payload, encode_key, algorithm=algo)


def create_refresh_token(data: dict) -> str:
    import uuid

    now = datetime.now(timezone.utc)
    payload = {
        "sub": data.get("sub"),
        "email": data.get("email"),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    encode_key = _get_encode_key()
    algo = JWT_ALGORITHM if (JWT_ALGORITHM == "RS256" and _PRIVATE_KEY_BYTES) else "HS256"
    return jwt.encode(payload, encode_key, algorithm=algo)


# ── Token verification ─────────────────────────────────────────────────────────
def verify_token(token: str, expected_type: str = "access") -> dict:
    """
    Verify and decode a JWT token.
    Returns the payload dict on success, raises HTTPException on failure.
    """
    decode_key = _get_decode_key()
    algo = JWT_ALGORITHM if (JWT_ALGORITHM == "RS256" and _PUBLIC_KEY_BYTES) else "HS256"

    try:
        payload = jwt.decode(
            token,
            decode_key,
            algorithms=[algo],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Expected {expected_type} token",
        )

    return payload


# ── FastAPI dependency: get_current_user ──────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> TokenData:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials, expected_type="access")
    role = payload.get("role", "viewer")
    permissions = ROLE_PERMISSIONS.get(role, set())

    return TokenData(
        user_id=payload["sub"],
        email=payload.get("email", ""),
        role=role,
        full_name=payload.get("full_name", ""),
        permissions=permissions,
        jti=payload["jti"],
    )


def require_permission(permission: str):
    """Dependency factory: verifies the current user has a specific permission."""

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user

    return _check


def require_role(*roles: str):
    """Dependency factory: verifies the current user has one of the required roles."""

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {roles} required, got '{user.role}'",
            )
        return user

    return _check


# ── JWT Auth Middleware ───────────────────────────────────────────────────────
class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces JWT authentication for all routes
    except those in PUBLIC_PATHS / PUBLIC_PATH_PREFIXES.
    Attaches the decoded payload to request.state.user.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        # OPTIONS pre-flight
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Not authenticated", "path": path},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.split(" ", 1)[1]
        try:
            payload = verify_token(token, expected_type="access")
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
                headers=getattr(exc, "headers", {}),
            )

        role = payload.get("role", "viewer")
        request.state.user = TokenData(
            user_id=payload["sub"],
            email=payload.get("email", ""),
            role=role,
            full_name=payload.get("full_name", ""),
            permissions=ROLE_PERMISSIONS.get(role, set()),
            jti=payload["jti"],
        )
        request.state.user_id = payload["sub"]

        return await call_next(request)


# ── Token refresh router ───────────────────────────────────────────────────────
refresh_token_endpoint = APIRouter()


@refresh_token_endpoint.post("/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_access_token(body: RefreshRequest):
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    payload = verify_token(body.refresh_token, expected_type="refresh")

    new_access = create_access_token(
        {
            "sub": payload["sub"],
            "email": payload.get("email", ""),
            "role": payload.get("role", "viewer"),
            "full_name": payload.get("full_name", ""),
        }
    )
    new_refresh = create_refresh_token(
        {"sub": payload["sub"], "email": payload.get("email", "")}
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@refresh_token_endpoint.post("/logout", tags=["Auth"])
async def logout(user: TokenData = Depends(get_current_user)):
    """
    Logout endpoint — in production this should add the JTI to a Redis blacklist.
    """
    # TODO: add payload["jti"] to Redis blacklist with TTL = remaining token lifetime
    logger.info("User %s logged out (jti=%s)", user.user_id, user.jti)
    return {"message": "Logged out successfully"}
