import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response, Cookie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from ..db import get_db
from ..security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    hash_token,
)
from ..models.user import User, RefreshToken

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    message: str


@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    user = User(
        id=str(uuid.uuid4()),
        email=request.email,
        password_hash=get_password_hash(request.password)
    )
    db.add(user)
    await db.commit()

    return {"message": "User registered successfully"}


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login a user and set HTTP-only cookies."""
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create access token
    access_token = create_access_token({"sub": user.id})

    # Create and store refresh token
    refresh_token, expires_at = create_refresh_token()
    token_hash = hash_token(refresh_token)

    # Delete old refresh tokens for this user
    await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    for old_token in (await db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))).scalars().all():
        await db.delete(old_token)

    # Store new refresh token
    db_refresh_token = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(db_refresh_token)
    await db.commit()

    # Set HTTP-only cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=15 * 60  # 15 minutes
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )

    return {"message": "Login successful"}


@router.post("/refresh")
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str = Cookie(None),
    access_token: str = Cookie(None)
):
    """Refresh access token using refresh token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    # Find the refresh token in database
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Create new access token
    new_access_token = create_access_token({"sub": db_token.user_id})

    # Update access token cookie
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=15 * 60
    )

    return {"message": "Token refreshed"}


@router.post("/logout")
async def logout(response: Response):
    """Clear auth cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logout successful"}
