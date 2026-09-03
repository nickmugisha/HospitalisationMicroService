from __future__ import annotations

import getpass
import secrets
import uuid
from datetime import date, timedelta

import grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from hr.v1 import hr_pb2, hr_pb2_grpc

AUTH = "127.0.0.1:50051"
HR = "127.0.0.1:50062"


def md(token):
    return (("authorization", f"Bearer {token}"),)


def ok(label):
    print("[OK]", label)


def expect(code, fn, label):
    try:
        fn()
    except grpc.RpcError as exc:
        if exc.code() != code:
            raise AssertionError(
                f"{label}: expected {code.name}, got {exc.code().name}: {exc.details()}"
            )
        ok(label)
        return
    raise AssertionError(label + ": unexpectedly succeeded")


def cleanup_abandoned_v3_fixtures(hr, metadata):
    """Clean only fixtures created by this regression family (employee_number PXV3-*)."""
    cleaned = 0
    try:
        employees = hr.ListEmployees(
            hr_pb2.ListEmployeesRequest(limit=200, offset=0),
            metadata=metadata,
            timeout=5,
        ).employees
    except grpc.RpcError:
        return 0

    today = date.today()
    horizon = today + timedelta(days=60)
    for employee in employees:
        if not employee.employee_number.startswith("PXV3-"):
            continue
        if employee.employment_status == hr_pb2.EMPLOYMENT_STATUS_TERMINATED:
            continue
        try:
            shifts = hr.ListShifts(
                hr_pb2.ListShiftsRequest(
                    employee_id=employee.id,
                    from_date=today.isoformat(),
                    to_date=horizon.isoformat(),
                    limit=200,
                ),
                metadata=metadata,
                timeout=5,
            ).shifts
            for shift in shifts:
                if shift.status == hr_pb2.SHIFT_STATUS_SCHEDULED:
                    try:
                        hr.CancelShift(
                            hr_pb2.CancelShiftRequest(
                                shift_id=shift.id,
                                reason="cleanup abandoned v3 regression fixture",
                            ),
                            metadata=metadata,
                            timeout=5,
                        )
                    except grpc.RpcError:
                        pass
            hr.SetEmploymentStatus(
                hr_pb2.SetEmploymentStatusRequest(
                    employee_id=employee.id,
                    status=hr_pb2.EMPLOYMENT_STATUS_TERMINATED,
                    reason="cleanup abandoned v3 regression fixture",
                ),
                metadata=metadata,
                timeout=5,
            )
            cleaned += 1
        except grpc.RpcError:
            # Cleanup must never hide the real regression result.
            pass
    return cleaned


def main():
    admin_username = input("Admin username: ").strip()
    admin_password = getpass.getpass("Admin password: ")

    suffix = uuid.uuid4().hex[:8]
    username = f"v3staff_{suffix}"
    password = secrets.token_urlsafe(14)
    employee_number = f"PXV3-{suffix.upper()}"
    today = date.today()
    tomorrow = today + timedelta(days=1)

    employee = None
    future_shift = None
    guard_shift = None
    terminated = False
    admin_md = None

    with grpc.insecure_channel(AUTH) as auth_channel, grpc.insecure_channel(HR) as hr_channel:
        auth = auth_pb2_grpc.AuthServiceStub(auth_channel)
        hr = hr_pb2_grpc.HRServiceStub(hr_channel)

        admin = auth.Login(
            auth_pb2.LoginRequest(username=admin_username, password=admin_password),
            timeout=5,
        )
        admin_md = md(admin.access_token)
        ok("Admin login")

        cleaned = cleanup_abandoned_v3_fixtures(hr, admin_md)
        if cleaned:
            ok(f"Cleaned {cleaned} abandoned PXV3 regression fixture(s)")

        try:
            registration = hr.RegisterEmployee(
                hr_pb2.RegisterEmployeeRequest(
                    employee_number=employee_number,
                    first_name="Night",
                    last_name="ShiftTest",
                    email=f"{username}@projectx.test",
                    phone="+25700000000",
                    department="Consultation",
                    job_title="Médecin test",
                    hire_date=today.isoformat(),
                    employment_type="PERMANENT",
                    username=username,
                    temporary_password=password,
                ),
                metadata=admin_md,
                timeout=8,
            )
            employee = registration.employee

            approval = auth.ApproveUser(
                auth_pb2.ApproveUserRequest(
                    user_id=employee.auth_user_id,
                    role_codes=["MEDECIN"],
                ),
                metadata=admin_md,
                timeout=5,
            )
            qr_payload = approval.qr_payload
            ok("Test employee approved as MEDECIN")

            user = auth.Login(
                auth_pb2.LoginRequest(username=username, password=password),
                timeout=5,
            )
            user_md = md(user.access_token)
            ok("Employee login")

            future_shift = hr.CreateShift(
                hr_pb2.CreateShiftRequest(
                    employee_id=employee.id,
                    shift_date=tomorrow.isoformat(),
                    start_time="20:00",
                    end_time="08:00",
                    location="Urgences",
                    idempotency_key=f"overnight-{suffix}",
                ),
                metadata=admin_md,
                timeout=5,
            ).shift
            assert future_shift.overnight
            ok("Overnight shift 20:00 -> 08:00 accepted")

            expect(
                grpc.StatusCode.ALREADY_EXISTS,
                lambda: hr.CreateShift(
                    hr_pb2.CreateShiftRequest(
                        employee_id=employee.id,
                        shift_date=tomorrow.isoformat(),
                        start_time="22:00",
                        end_time="06:00",
                        location="Urgences",
                        idempotency_key=f"overlap-{suffix}",
                    ),
                    metadata=admin_md,
                    timeout=5,
                ),
                "Overlapping overnight shift rejected",
            )

            mine = hr.ListMyShifts(
                hr_pb2.ListMyShiftsRequest(
                    from_date=tomorrow.isoformat(),
                    to_date=tomorrow.isoformat(),
                    limit=20,
                ),
                metadata=user_md,
                timeout=5,
            )
            assert any(x.id == future_shift.id and x.overnight for x in mine.shifts)
            ok("Employee self-read of shifts")

            # Guard 1: a future work date is an invalid request.
            expect(
                grpc.StatusCode.INVALID_ARGUMENT,
                lambda: hr.FinalizeAttendanceDay(
                    hr_pb2.FinalizeAttendanceDayRequest(
                        work_date=tomorrow.isoformat(),
                        reason="future-day v3 regression",
                    ),
                    metadata=admin_md,
                    timeout=5,
                ),
                "Future attendance-day finalization rejected",
            )

            # Guard 2: today's attendance cannot be finalized while a scheduled
            # overnight shift still ends tomorrow. This exercises the actual
            # FAILED_PRECONDITION branch rather than confusing it with Guard 1.
            guard_shift = hr.CreateShift(
                hr_pb2.CreateShiftRequest(
                    employee_id=employee.id,
                    shift_date=today.isoformat(),
                    start_time="20:00",
                    end_time="08:00",
                    location="Premature-close guard",
                    idempotency_key=f"close-guard-{suffix}",
                ),
                metadata=admin_md,
                timeout=5,
            ).shift
            assert guard_shift.overnight
            expect(
                grpc.StatusCode.FAILED_PRECONDITION,
                lambda: hr.FinalizeAttendanceDay(
                    hr_pb2.FinalizeAttendanceDayRequest(
                        work_date=today.isoformat(),
                        reason="premature v3 regression",
                    ),
                    metadata=admin_md,
                    timeout=5,
                ),
                "Premature attendance-day finalization blocked",
            )
            hr.CancelShift(
                hr_pb2.CancelShiftRequest(
                    shift_id=guard_shift.id,
                    reason="v3 close-guard cleanup",
                ),
                metadata=admin_md,
                timeout=5,
            )
            guard_shift = None
            ok("Premature-close guard shift cancelled")

            updated = hr.UpdateEmployee(
                hr_pb2.UpdateEmployeeRequest(
                    employee_id=employee.id,
                    first_name="NightUpdated",
                    last_name="ShiftTest",
                    email=f"{username}@projectx.test",
                    phone="+25700000001",
                    department="Consultation",
                    job_title="Médecin de garde",
                    employment_type="PERMANENT",
                ),
                metadata=admin_md,
                timeout=5,
            ).employee
            entry = auth.GetStaffDirectoryEntry(
                auth_pb2.GetStaffDirectoryEntryRequest(user_id=updated.auth_user_id),
                metadata=admin_md,
                timeout=5,
            ).entry
            assert entry.display_name.startswith("NightUpdated")
            assert entry.job_title == "Médecin de garde"
            ok("HR profile changes synchronized to Auth directory")

            leave = hr.SubmitLeaveRequest(
                hr_pb2.SubmitLeaveRequestRequest(
                    leave_type="ANNUAL",
                    start_date=(tomorrow + timedelta(days=10)).isoformat(),
                    end_date=(tomorrow + timedelta(days=11)).isoformat(),
                    reason="v3 self-service test",
                ),
                metadata=user_md,
                timeout=5,
            ).leave_request
            listed = hr.ListMyLeaveRequests(
                hr_pb2.ListMyLeaveRequestsRequest(status="PENDING", limit=20),
                metadata=user_md,
                timeout=5,
            )
            assert any(x.id == leave.id for x in listed.leave_requests)
            ok("Employee self-read of leave requests")

            cancelled = hr.CancelMyLeaveRequest(
                hr_pb2.CancelMyLeaveRequestRequest(
                    leave_request_id=leave.id,
                    reason="v3 cleanup",
                ),
                metadata=user_md,
                timeout=5,
            ).leave_request
            assert cancelled.status == hr_pb2.LEAVE_STATUS_CANCELLED
            ok("Employee cancellation of own pending leave")

            hr.SetEmploymentStatus(
                hr_pb2.SetEmploymentStatusRequest(
                    employee_id=employee.id,
                    status=hr_pb2.EMPLOYMENT_STATUS_SUSPENDED,
                    reason="v3 suspension security test",
                ),
                metadata=admin_md,
                timeout=5,
            )
            expect(
                grpc.StatusCode.PERMISSION_DENIED,
                lambda: auth.Login(
                    auth_pb2.LoginRequest(username=username, password=password), timeout=5
                ),
                "HR suspension disables Auth credential login",
            )
            expect(
                grpc.StatusCode.PERMISSION_DENIED,
                lambda: auth.LoginWithQr(
                    auth_pb2.QrLoginRequest(qr_payload=qr_payload), timeout=5
                ),
                "HR suspension blocks QR login without revoking credential",
            )

            hr.SetEmploymentStatus(
                hr_pb2.SetEmploymentStatusRequest(
                    employee_id=employee.id,
                    status=hr_pb2.EMPLOYMENT_STATUS_ACTIVE,
                    reason="v3 reactivate after suspension",
                ),
                metadata=admin_md,
                timeout=5,
            )
            user2 = auth.Login(
                auth_pb2.LoginRequest(username=username, password=password), timeout=5
            )
            assert user2.user.status == auth_pb2.USER_STATUS_ACTIVE
            ok("HR reactivation restores approved Auth account")

            qr_login = auth.LoginWithQr(
                auth_pb2.QrLoginRequest(qr_payload=qr_payload), timeout=5
            )
            assert qr_login.user.status == auth_pb2.USER_STATUS_ACTIVE
            ok("QR credential works again after reactivation")

            logs = hr.ListHrAuditLogs(
                hr_pb2.ListHrAuditLogsRequest(resource_id=employee.id, limit=100),
                metadata=admin_md,
                timeout=5,
            )
            assert logs.total >= 1
            ok("HR audit log exposed")

            hr.CancelShift(
                hr_pb2.CancelShiftRequest(
                    shift_id=future_shift.id,
                    reason="v3 cleanup",
                ),
                metadata=admin_md,
                timeout=5,
            )
            future_shift = None
            ok("Future test shift cancelled")

            hr.SetEmploymentStatus(
                hr_pb2.SetEmploymentStatusRequest(
                    employee_id=employee.id,
                    status=hr_pb2.EMPLOYMENT_STATUS_TERMINATED,
                    reason="v3 cleanup termination",
                ),
                metadata=admin_md,
                timeout=5,
            )
            terminated = True
            expect(
                grpc.StatusCode.PERMISSION_DENIED,
                lambda: auth.Login(
                    auth_pb2.LoginRequest(username=username, password=password), timeout=5
                ),
                "Termination blocks credential login",
            )
            expect(
                grpc.StatusCode.UNAUTHENTICATED,
                lambda: auth.LoginWithQr(
                    auth_pb2.QrLoginRequest(qr_payload=qr_payload), timeout=5
                ),
                "Termination revokes QR login",
            )

        finally:
            # Best-effort cleanup on any later assertion/RPC failure. We preserve
            # HR history; the test employee is terminated rather than deleted.
            if employee is not None and admin_md is not None:
                for candidate in (guard_shift, future_shift):
                    if candidate is not None:
                        try:
                            hr.CancelShift(
                                hr_pb2.CancelShiftRequest(
                                    shift_id=candidate.id,
                                    reason="v3 regression emergency cleanup",
                                ),
                                metadata=admin_md,
                                timeout=5,
                            )
                        except grpc.RpcError:
                            pass
                if not terminated:
                    try:
                        hr.SetEmploymentStatus(
                            hr_pb2.SetEmploymentStatusRequest(
                                employee_id=employee.id,
                                status=hr_pb2.EMPLOYMENT_STATUS_TERMINATED,
                                reason="v3 regression emergency cleanup",
                            ),
                            metadata=admin_md,
                            timeout=5,
                        )
                    except grpc.RpcError:
                        pass

    print("\nPROJECTX BACKEND COMPLETION V3 HR SECURITY/LIFECYCLE: PASS")


if __name__ == "__main__":
    main()
