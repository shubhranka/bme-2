import uuid
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt

# Password hashing functions using bcrypt directly
def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# JWT settings
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")


def create_access_token(data: dict) -> str:
    """Create an access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, datetime]:
    """Create a refresh token and return token and expiry."""
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify an access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
