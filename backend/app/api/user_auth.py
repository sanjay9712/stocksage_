"""User authentication endpoints — register, login, current user.

These endpoints do NOT require auth. All other /api/* endpoints
validate the JWT via `require_token` in auth.py.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import create_access_token, hash_password, require_token, verify_password
from app.db import User, get_db
from app.models import LoginRequest, RegisterRequest, TokenResponse, UserOut

log = logging.getLogger("user_auth")
router = APIRouter()


@router.post("/auth/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user. Returns JWT + user info."""
    # Step 1: Validate name.
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")

    # Step 2: Validate email format.
    email = payload.email.lower().strip()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid email address")

    # Step 3: Check if email already registered.
    existing = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email is already registered. Please log in.")

    # Step 4: Validate password.
    if len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    # Step 5: Validate capital.
    if payload.capital not in (500000.0, 1000000.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capital must be 5,00,000 or 10,00,000")

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        capital=payload.capital,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    return TokenResponse(
        token=token,
        user=UserOut(id=user.id, name=user.name, email=user.email, capital=user.capital, is_guest=user.is_guest, created_at=user.created_at),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login with email + password. Returns JWT + user info."""
    # Step 0: Validate email format and password presence.
    if not payload.email or not payload.email.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is required")

    email = payload.email.lower().strip()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid email address")

    # Step 1: Check if account exists.
    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email. Please register first.",
        )

    # Step 2: Verify password.
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again.",
        )

    token = create_access_token(user)
    return TokenResponse(
        token=token,
        user=UserOut(id=user.id, name=user.name, email=user.email, capital=user.capital, is_guest=user.is_guest, created_at=user.created_at),
    )


@router.post("/auth/guest", response_model=TokenResponse)
async def guest_login(db: Session = Depends(get_db)):
    """Create a temporary guest user. Can browse the app but cannot access
    paper trading or funds. No email/password required."""
    import uuid
    guest_email = f"guest_{uuid.uuid4().hex[:8]}@guest.local"
    user = User(
        email=guest_email,
        name="Guest",
        password_hash="!",  # No password — guests can't log in normally
        capital=0.0,
        is_guest=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    return TokenResponse(
        token=token,
        user=UserOut(id=user.id, name=user.name, email=user.email, capital=user.capital, is_guest=user.is_guest, created_at=user.created_at),
    )


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(require_token)):
    """Return the current authenticated user's info."""
    return UserOut(id=user.id, name=user.name, email=user.email, capital=user.capital, is_guest=user.is_guest, created_at=user.created_at)
