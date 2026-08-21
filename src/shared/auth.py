"""
src/shared/auth.py — AutoMark AI (unified)

App-wide identity: bcrypt password hashing + HS256 JWTs, plus the FastAPI
dependencies every module uses to resolve the current user.

Promoted from the campaign module — the `users` table is now the single
identity for campaigns, analytics, and any authenticated CRM admin route.

JWT_SECRET must be set in .env for production use.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select

from src.config import settings
from src.shared.db import async_session
from src.shared.models import User

logger = logging.getLogger(__name__)


# ── Passwords ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), pw_hash.encode("utf-8"))
    except Exception:
        return False


# ── Tokens ───────────────────────────────────────────────────────────────────

def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return {"user_id": str, "email": str} or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return {"user_id": payload["sub"], "email": payload["email"]}
    except Exception:
        return None


# ── FastAPI dependencies ─────────────────────────────────────────────────────

def extract_user(authorization: Optional[str]) -> dict | None:
    """Pull user info from an 'Bearer <token>' header. None if absent/invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return decode_token(authorization[7:])


async def current_user_optional(
    authorization: Optional[str] = Header(None),
) -> dict | None:
    """Resolve the caller if a valid token is present; otherwise None."""
    return extract_user(authorization)


async def require_user(authorization: Optional[str] = Header(None)) -> dict:
    """Resolve the caller, or 401."""
    user = extract_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ── User persistence ─────────────────────────────────────────────────────────

async def create_user(email: str, password: str) -> dict:
    """Register a new account. Raises HTTPException(409) on duplicate email."""
    email = email.lower().strip()
    async with async_session() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already registered")
        user = User(email=email, pw_hash=hash_password(password))
        session.add(user)
        await session.flush()
        return {"id": str(user.id), "email": user.email}


async def authenticate(email: str, password: str) -> dict:
    """Verify credentials and return {"id", "email"}. Raises 401 on failure."""
    email = email.lower().strip()
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.pw_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"id": str(user.id), "email": user.email}
