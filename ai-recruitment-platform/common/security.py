"""Security utilities: JWT, password hashing, RBAC."""
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from common.config import settings
from common.exceptions import ForbiddenException, UnauthorizedException


class UserRole(str, Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    VIEWER = "viewer"


class TokenData(BaseModel):
    user_id: str
    email: str
    role: UserRole
    exp: Optional[datetime] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.jwt_access_token_expire_minutes * 60


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    user_id: str,
    email: str,
    role: UserRole,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role.value,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    payload: Dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise UnauthorizedException(f"Invalid token: {e}")


def verify_access_token(token: str) -> TokenData:
    """Verify an access token and return token data."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type")
    return TokenData(
        user_id=payload["sub"],
        email=payload["email"],
        role=UserRole(payload["role"]),
    )


def create_token_pair(user_id: str, email: str, role: UserRole) -> TokenPair:
    """Create both access and refresh tokens."""
    return TokenPair(
        access_token=create_access_token(user_id, email, role),
        refresh_token=create_refresh_token(user_id),
    )


class RBACChecker:
    """Role-based access control checker."""

    ROLE_PERMISSIONS: Dict[UserRole, List[str]] = {
        UserRole.ADMIN: ["*"],
        UserRole.RECRUITER: [
            "employers:read", "employers:write",
            "candidates:read", "candidates:write",
            "outreach:read", "outreach:write",
            "crm:read", "crm:write",
            "analytics:read",
            "settings:read", "settings:write",
        ],
        UserRole.VIEWER: [
            "employers:read",
            "candidates:read",
            "outreach:read",
            "crm:read",
            "analytics:read",
        ],
    }

    @classmethod
    def check_permission(cls, role: UserRole, permission: str) -> bool:
        """Check if a role has a specific permission."""
        permissions = cls.ROLE_PERMISSIONS.get(role, [])
        if "*" in permissions:
            return True
        return permission in permissions

    @classmethod
    def require_permission(cls, role: UserRole, permission: str) -> None:
        """Raise ForbiddenException if role lacks permission."""
        if not cls.check_permission(role, permission):
            raise ForbiddenException(
                f"Role '{role.value}' does not have permission '{permission}'"
            )


rbac = RBACChecker()
