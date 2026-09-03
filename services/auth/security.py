from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
import secrets

import bcrypt
import jwt

from services.auth.config import JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, JWT_SECRET

QR_PREFIX = "PROJECTX-QR1:"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(*, user_id: str, username: str, roles: list[str], permissions: list[str], auth_version: int = 1) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "permissions": permissions,
        "auth_version": int(auth_version or 1),
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    if not token:
        raise jwt.InvalidTokenError("Token is missing.")
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type.")
    return payload


def generate_qr_payload() -> tuple[str, str]:
    # 256 bits of random entropy. The raw value is returned only once.
    raw_token = secrets.token_urlsafe(32)
    payload = f"{QR_PREFIX}{raw_token}"
    return payload, qr_payload_hash(payload)


def qr_payload_hash(payload: str) -> str:
    value = payload.strip()
    if not value.startswith(QR_PREFIX):
        raise ValueError("Invalid QR payload format.")
    return sha256(value.encode("utf-8")).hexdigest()
