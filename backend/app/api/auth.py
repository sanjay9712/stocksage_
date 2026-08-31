"""JWT-based per-user authentication.

Users register/login to get a JWT. The token is sent as
`Authorization: Bearer <jwt>`. `require_token` validates the JWT,
looks up the user, and returns the `User` object. Existing endpoints
that use `_t: str = Depends(require_token)` keep working — they
just ignore the returned User.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import User, get_db


def hash_password(password: str) -> str:
    """Bcrypt hash a plaintext password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user: User) -> str:
    """Create a JWT containing user_id, capital, and guest flag."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "capital": user.capital,
        "is_guest": user.is_guest,
        "exp": expire,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(authorization: str | None) -> dict:
    """Decode and validate a JWT from the Authorization header.
    Returns the payload dict. Raises HTTPException on invalid/expired tokens.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")
    try:
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


async def require_token(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Validate JWT and return the authenticated User object."""
    payload = decode_token(authorization)
    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_user(
    user: User = Depends(require_token),
) -> User:
    """Like require_token, but rejects guest users.
    Use this for endpoints that need a registered user (paper trading, funds)."""
    if user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot access this feature. Please register or log in.",
        )
    return user
