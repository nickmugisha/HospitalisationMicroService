from __future__ import annotations

from google.protobuf.timestamp_pb2 import Timestamp
import grpc
import jwt

from auth.v1 import auth_pb2
from auth.v1 import auth_pb2_grpc

from database.session import SessionLocal
from services.auth.repository import (
    collect_user_permissions,
    collect_user_roles,
    get_user_by_id,
    get_user_by_username,
)
from services.auth.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)


def datetime_to_timestamp(value):
    timestamp = Timestamp()
    timestamp.FromDatetime(value)
    return timestamp


def user_to_proto(user):
    roles = collect_user_roles(user)
    permissions = collect_user_permissions(user)

    status = (
        auth_pb2.USER_STATUS_ACTIVE
        if user.active
        else auth_pb2.USER_STATUS_DISABLED
    )

    return auth_pb2.User(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=status,
        roles=roles,
        permissions=permissions,
    )


class AuthService(
    auth_pb2_grpc.AuthServiceServicer
):

    # ======================================================
    # LOGIN
    # ======================================================

    def Login(self, request, context):
        username = request.username.strip()
        password = request.password

        if not username or not password:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Username and password are required.",
            )

        session = SessionLocal()

        try:
            user = get_user_by_username(
                session,
                username,
            )

            # Do not reveal whether the username
            # or password was incorrect.
            if user is None:
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    "Invalid username or password.",
                )

            if not user.active:
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    "This account is disabled.",
                )

            if not verify_password(
                password,
                user.password_hash,
            ):
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    "Invalid username or password.",
                )

            roles = collect_user_roles(user)
            permissions = collect_user_permissions(user)

            access_token, expires_at = create_access_token(
                user_id=user.id,
                username=user.username,
                roles=roles,
                permissions=permissions,
            )

            return auth_pb2.LoginResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_at=datetime_to_timestamp(
                    expires_at
                ),
                user=user_to_proto(user),
            )

        finally:
            session.close()


    # ======================================================
    # VALIDATE TOKEN
    # ======================================================

    def ValidateToken(self, request, context):
        access_token = request.access_token.strip()

        if not access_token:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Access token is required.",
            )

        try:
            payload = decode_access_token(
                access_token
            )

        except jwt.ExpiredSignatureError:
            return auth_pb2.ValidateTokenResponse(
                valid=False
            )

        except jwt.InvalidTokenError:
            return auth_pb2.ValidateTokenResponse(
                valid=False
            )

        user_id = payload.get("sub")

        if (
            not isinstance(user_id, str)
            or not user_id.strip()
        ):
            return auth_pb2.ValidateTokenResponse(
                valid=False
            )

        session = SessionLocal()

        try:
            user = get_user_by_id(
                session,
                user_id,
            )

            if user is None:
                return auth_pb2.ValidateTokenResponse(
                    valid=False
                )

            if not user.active:
                return auth_pb2.ValidateTokenResponse(
                    valid=False
                )

            return auth_pb2.ValidateTokenResponse(
                valid=True,
                user=user_to_proto(user),
            )

        finally:
            session.close()