from __future__ import annotations

import os

import grpc
from dotenv import load_dotenv

from auth.v1 import auth_pb2, auth_pb2_grpc


load_dotenv()
AUTH_GRPC_TARGET = os.getenv("AUTH_GRPC_TARGET", "127.0.0.1:50051")


def _extract_bearer_token(context) -> str:
    metadata = {item.key.lower(): item.value for item in context.invocation_metadata()}
    raw = metadata.get("authorization", "").strip()
    if not raw:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization metadata.")
    if not raw.lower().startswith("bearer "):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Authorization must use Bearer token.")
    token = raw[7:].strip()
    if not token:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing access token.")
    return token


def require_permission(context, permission_code: str):
    token = _extract_bearer_token(context)

    try:
        with grpc.insecure_channel(AUTH_GRPC_TARGET) as channel:
            stub = auth_pb2_grpc.AuthServiceStub(channel)
            response = stub.ValidateToken(
                auth_pb2.ValidateTokenRequest(access_token=token),
                timeout=3,
            )
    except grpc.RpcError as error:
        context.abort(
            grpc.StatusCode.UNAVAILABLE,
            f"Authentication service unavailable: {error.code().name}",
        )

    if not response.valid:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or expired access token.")

    if permission_code not in set(response.user.permissions):
        context.abort(
            grpc.StatusCode.PERMISSION_DENIED,
            f"Missing permission: {permission_code}",
        )

    return response.user
