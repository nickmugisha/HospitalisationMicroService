from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from services.auth.config import (
    JWT_ALGORITHM,
    JWT_EXPIRATION_MINUTES,
    JWT_SECRET,
)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")

    encoded = password.encode("utf-8")

    hashed = bcrypt.hashpw(
        encoded,
        bcrypt.gensalt(),
    )

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: str,
    username: str,
    roles: list[str],
    permissions: list[str],
) -> tuple[str, datetime]:

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes=JWT_EXPIRATION_MINUTES
    )

    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "permissions": permissions,
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    return token, expires_at


def decode_access_token(
    token: str,
) -> dict[str, Any]:

    if not token:
        raise jwt.InvalidTokenError(
            "Token is missing."
        )

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError(
            "Invalid token type."
        )

    return payload