from typing import Optional
from fastapi import HTTPException, Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..security import decode_access_token, hash_token
from ..models.user import User, RefreshToken


async def get_current_user(
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get the current authenticated user."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Decode access token
    payload = decode_access_token(access_token)
    if not payload:
        # Try to refresh using refresh token
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_user(
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Dependency to get the current user if authenticated, otherwise None."""
    if not access_token:
        return None

    payload = decode_access_token(access_token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
