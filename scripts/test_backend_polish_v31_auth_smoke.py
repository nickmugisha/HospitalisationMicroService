from __future__ import annotations

import getpass
import uuid

import grpc

from auth.v1 import auth_pb2, auth_pb2_grpc


def md(token: str):
    return (("authorization", f"Bearer {token}"),)


def expect(code, fn, label):
    try:
        fn()
    except grpc.RpcError as exc:
        if exc.code() != code:
            raise AssertionError(f"{label}: expected {code.name}, got {exc.code().name}: {exc.details()}")
        print(f"[OK] {label}")
        return
    raise AssertionError(f"{label}: RPC unexpectedly succeeded")


def main():
    suffix = uuid.uuid4().hex[:8]
    username = f"px31.user.{suffix}"
    employee_number = f"PX31-{suffix.upper()}"
    email1 = f"{username}@projectx.test"
    email2 = f"{username}.updated@projectx.test"
    old_password = "PX31-Demo-123!"
    new_password = "PX31-New-456!"

    admin_username = input("Admin username: ").strip() or "admin"
    admin_password = getpass.getpass("Admin password: ")

    channel = grpc.insecure_channel("127.0.0.1:50051")
    auth = auth_pb2_grpc.AuthServiceStub(channel)
    test_user_id = ""
    admin_token = ""
    try:
        admin_login = auth.Login(auth_pb2.LoginRequest(username=admin_username, password=admin_password), timeout=5)
        admin_token = admin_login.access_token
        amd = md(admin_token)
        print("[OK] Legacy username login remains compatible")

        created = auth.RegisterStaff(
            auth_pb2.RegisterStaffRequest(
                employee_number=employee_number,
                first_name="Polish",
                last_name="Regression",
                email=email1,
                phone="+257790031001",
                department="Consultation",
                job_title="Medecin Test",
                username=username,
                temporary_password=old_password,
            ), metadata=amd, timeout=5,
        )
        test_user_id = created.user.id
        approved = auth.ApproveUser(
            auth_pb2.ApproveUserRequest(user_id=test_user_id, role_codes=["MEDECIN"]),
            metadata=amd, timeout=5,
        )
        assert "MEDECIN" in approved.user.roles
        print("[OK] Controlled test staff approved")

        user_login = auth.Login(auth_pb2.LoginRequest(username=username, password=old_password), timeout=5)
        token1 = user_login.access_token
        print("[OK] Username login")

        updated = auth.UpdateMyProfile(
            auth_pb2.UpdateMyProfileRequest(email=email2, phone="+257790031002"),
            metadata=md(token1), timeout=5,
        )
        assert updated.user.staff_profile.email == email2
        assert updated.user.staff_profile.phone == "+257790031002"
        assert updated.user.staff_profile.department == "Consultation"
        assert updated.user.staff_profile.job_title == "Medecin Test"
        print("[OK] Self profile updates only safe personal fields")

        email_login = auth.Login(auth_pb2.LoginRequest(identifier=email2, password=old_password), timeout=5)
        token2 = email_login.access_token
        assert email_login.user.username == username
        print("[OK] Email login")

        changed = auth.ChangeMyPassword(
            auth_pb2.ChangeMyPasswordRequest(current_password=old_password, new_password=new_password),
            metadata=md(token2), timeout=5,
        )
        assert changed.changed and changed.reauthentication_required
        print("[OK] Password change")

        assert not auth.ValidateToken(auth_pb2.ValidateTokenRequest(access_token=token2), timeout=5).valid
        print("[OK] Pre-change JWT invalidated")

        expect(
            grpc.StatusCode.UNAUTHENTICATED,
            lambda: auth.Login(auth_pb2.LoginRequest(identifier=email2, password=old_password), timeout=5),
            "Old password rejected",
        )
        relogin = auth.Login(auth_pb2.LoginRequest(identifier=email2, password=new_password), timeout=5)
        assert relogin.user.id == test_user_id
        print("[OK] New password + email login")

        auth.RevokeQrCredential(auth_pb2.RevokeQrCredentialRequest(user_id=test_user_id), metadata=amd, timeout=5)
        auth.DisableUser(auth_pb2.DisableUserRequest(user_id=test_user_id, reason="v3.1 regression cleanup"), metadata=amd, timeout=5)
        print("[OK] Test account disabled and QR revoked")
        test_user_id = ""

        print("\nPROJECTX BACKEND POLISH V3.1 AUTH SELF-SERVICE SMOKE: PASS")
    finally:
        # Best-effort cleanup if the test stops after account creation.
        if test_user_id and admin_token:
            try:
                auth.RevokeQrCredential(auth_pb2.RevokeQrCredentialRequest(user_id=test_user_id), metadata=md(admin_token), timeout=3)
            except grpc.RpcError:
                pass
            try:
                auth.DisableUser(auth_pb2.DisableUserRequest(user_id=test_user_id, reason="v3.1 failed regression cleanup"), metadata=md(admin_token), timeout=3)
            except grpc.RpcError:
                pass
        channel.close()


if __name__ == "__main__":
    main()
