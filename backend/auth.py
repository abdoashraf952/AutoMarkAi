"""
Simple email/password authentication — bcrypt + PyJWT.

hash_password / verify_password   — bcrypt wrappers
create_token / decode_token       — HS256 JWT, 7-day expiry

JWT_SECRET must be set in .env for production use.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

logger = logging.getLogger(__name__)

_SECRET    = os.getenv("JWT_SECRET", "automark-dev-secret-CHANGE-IN-PRODUCTION")
_ALGORITHM = "HS256"
_EXPIRE_H  = 24 * 7   # 7 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), pw_hash.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_EXPIRE_H),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return {"user_id": str, "email": str} or None if invalid/expired."""
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        return {"user_id": payload["sub"], "email": payload["email"]}
    except Exception:
        return None
