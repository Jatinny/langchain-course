"""Authentication routes for the API gateway."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.database import get_async_db
from common.security import (
    UserRole,
    TokenPair,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
    verify_access_token,
)
from common.exceptions import UnauthorizedException

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.RECRUITER


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    created_at: datetime


@router.post("/login", response_model=TokenPair)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db),
) -> TokenPair:
    """Authenticate user and return JWT tokens."""
    from sqlalchemy import select, text

    # In production, query the users table
    # This is a simplified version for demo
    result = await db.execute(
        text("SELECT id, email, hashed_password, role, full_name FROM users WHERE email = :email AND is_active = true"),
        {"email": form_data.username}
    )
    user = result.fetchone()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return create_token_pair(
        user_id=str(user.id),
        email=user.email,
        role=UserRole(user.role),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_async_db),
) -> UserResponse:
    """Register a new user account."""
    from sqlalchemy import text
    import uuid

    # Check if email exists
    result = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": request.email}
    )
    if result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user_id = str(uuid.uuid4())
    hashed_pwd = hash_password(request.password)
    now = datetime.now(timezone.utc)

    await db.execute(
        text("""
            INSERT INTO users (id, email, hashed_password, role, full_name, created_at, is_active)
            VALUES (:id, :email, :password, :role, :full_name, :created_at, true)
        """),
        {
            "id": user_id,
            "email": request.email,
            "password": hashed_pwd,
            "role": request.role.value,
            "full_name": request.full_name,
            "created_at": now,
        }
    )
    await db.commit()

    return UserResponse(
        id=user_id,
        email=request.email,
        full_name=request.full_name,
        role=request.role,
        created_at=now,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenPair:
    """Refresh access token using refresh token."""
    from sqlalchemy import text

    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type")

        user_id = payload["sub"]
        result = await db.execute(
            text("SELECT id, email, role FROM users WHERE id = :id AND is_active = true"),
            {"id": user_id}
        )
        user = result.fetchone()
        if not user:
            raise UnauthorizedException("User not found")

        return create_token_pair(
            user_id=str(user.id),
            email=user.email,
            role=UserRole(user.role),
        )
    except UnauthorizedException:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> UserResponse:
    """Get current user info from JWT token."""
    from sqlalchemy import text

    token_data = verify_access_token(token)
    result = await db.execute(
        text("SELECT id, email, role, full_name, created_at FROM users WHERE id = :id"),
        {"id": token_data.user_id}
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=UserRole(user.role),
        created_at=user.created_at,
    )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)) -> dict:
    """Logout (invalidate token via Redis blacklist)."""
    from common.redis_client import redis_client
    from common.security import decode_token

    try:
        payload = decode_token(token)
        exp = payload.get("exp", 0)
        remaining_ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp()))
        if remaining_ttl > 0:
            await redis_client.set(f"blacklist:{token}", "1", ttl=remaining_ttl)
    except Exception:
        pass  # Token already invalid

    return {"message": "Logged out successfully"}
