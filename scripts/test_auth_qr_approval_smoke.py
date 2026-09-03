from __future__ import annotations

import getpass
import secrets
import sys

import grpc

from auth.v1 import auth_pb2, auth_pb2_grpc

AUTH_TARGET = "127.0.0.1:50051"


def metadata(token: str):
    return (("authorization", f"Bearer {token}"),)


def expect_failure(callable_, allowed_codes):
    try:
        callable_()
    except grpc.RpcError as exc:
        if exc.code() not in allowed_codes:
            raise
        return exc.code()
    raise AssertionError("Expected the RPC to fail")


def main():
    print("PROJECTX Auth QR + approval smoke test")
    admin_username = input("Admin username: ").strip()
    admin_password = getpass.getpass("Admin password: ")
    if not admin_username or not admin_password:
        raise SystemExit("Admin credentials are required.")

    suffix = secrets.token_hex(4)
    username = f"qr_smoke_{suffix}"
    password = f"QrTest!{secrets.token_urlsafe(12)}"

    with grpc.insecure_channel(AUTH_TARGET) as channel:
        stub = auth_pb2_grpc.AuthServiceStub(channel)

        admin = stub.Login(
            auth_pb2.LoginRequest(username=admin_username, password=admin_password),
            timeout=5,
        )
        print("[OK] Admin credential login")

        registration = stub.Register(
            auth_pb2.RegisterRequest(
                username=username,
                password=password,
                display_name="QR Smoke User",
            ),
            timeout=5,
        )
        user_id = registration.user.id
        assert registration.user.status == auth_pb2.USER_STATUS_PENDING
        assert not registration.user.qr_enabled
        print("[OK] Registration creates PENDING account")

        code = expect_failure(
            lambda: stub.Login(
                auth_pb2.LoginRequest(username=username, password=password),
                timeout=5,
            ),
            {grpc.StatusCode.PERMISSION_DENIED},
        )
        print(f"[OK] Login blocked before admin approval ({code.name})")

        pending = stub.ListPendingUsers(
            auth_pb2.ListPendingUsersRequest(),
            metadata=metadata(admin.access_token),
            timeout=5,
        )
        assert any(item.id == user_id for item in pending.users)
        print("[OK] Admin sees pending registration")

        approval = stub.ApproveUser(
            auth_pb2.ApproveUserRequest(
                user_id=user_id,
                role_codes=["AGENT_ACCUEIL"],
            ),
            metadata=metadata(admin.access_token),
            timeout=5,
        )
        assert approval.user.status == auth_pb2.USER_STATUS_ACTIVE
        assert "AGENT_ACCUEIL" in approval.user.roles
        assert approval.qr_payload.startswith("PROJECTX-QR1:")
        qr_payload = approval.qr_payload
        print("[OK] Admin approval assigns role and issues QR")

        password_login = stub.Login(
            auth_pb2.LoginRequest(username=username, password=password),
            timeout=5,
        )
        assert password_login.dashboard_route == "/accueil"
        print("[OK] Approved user logs in with credentials -> /accueil")

        qr_login = stub.LoginWithQr(
            auth_pb2.QrLoginRequest(qr_payload=qr_payload),
            timeout=5,
        )
        assert qr_login.user.id == user_id
        assert qr_login.dashboard_route == "/accueil"
        print("[OK] Same approved user logs in with QR -> /accueil")

        stub.RevokeQrCredential(
            auth_pb2.RevokeQrCredentialRequest(user_id=user_id),
            metadata=metadata(admin.access_token),
            timeout=5,
        )
        code = expect_failure(
            lambda: stub.LoginWithQr(
                auth_pb2.QrLoginRequest(qr_payload=qr_payload),
                timeout=5,
            ),
            {grpc.StatusCode.UNAUTHENTICATED},
        )
        print(f"[OK] Revoked QR is rejected ({code.name})")

        stub.DisableUser(
            auth_pb2.DisableUserRequest(
                user_id=user_id,
                reason="QR smoke test cleanup",
            ),
            metadata=metadata(admin.access_token),
            timeout=5,
        )
        print("[OK] Test account disabled")

    print("\nPROJECTX QR AUTH + APPROVAL SMOKE TEST: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        raise
