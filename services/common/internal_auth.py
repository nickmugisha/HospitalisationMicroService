from __future__ import annotations

import hmac
import os

import grpc

INTERNAL_TOKEN_HEADER = "x-projectx-service-token"


def internal_service_token() -> str:
    value = os.getenv("PROJECTX_INTERNAL_SERVICE_TOKEN", "").strip()
    if not value:
        raise RuntimeError("Missing PROJECTX_INTERNAL_SERVICE_TOKEN")
    return value


def internal_metadata() -> tuple[tuple[str, str], ...]:
    return ((INTERNAL_TOKEN_HEADER, internal_service_token()),)


def require_internal_service(context) -> None:
    expected = internal_service_token()
    supplied = ""
    for item in context.invocation_metadata():
        if item.key.lower() == INTERNAL_TOKEN_HEADER:
            supplied = item.value.strip()
            break
    if not supplied or not hmac.compare_digest(supplied, expected):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid internal service credential.")
