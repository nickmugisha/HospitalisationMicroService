from __future__ import annotations
import getpass, secrets, uuid
from datetime import date, timedelta
import grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from hr.v1 import hr_pb2, hr_pb2_grpc

AUTH="127.0.0.1:50051"; HR="127.0.0.1:50062"
def md(token): return (("authorization",f"Bearer {token}"),)
def ok(x): print("[OK]",x)
def expect(code, fn, label):
    try: fn()
    except grpc.RpcError as e:
        if e.code()!=code: raise AssertionError(f"{label}: expected {code.name}, got {e.code().name}: {e.details()}")
        ok(label); return
    raise AssertionError(label+": unexpectedly succeeded")

def main():
    au=input("Admin username: ").strip(); ap=getpass.getpass("Admin password: ")
    suffix=uuid.uuid4().hex[:8]; hr_user=f"hrv22_{suffix}"; staff_user=f"staffv22_{suffix}"
    hr_pass=secrets.token_urlsafe(12); staff_pass=secrets.token_urlsafe(12); empno=f"PXHR-{suffix.upper()}"
    today=date.today()
    with grpc.insecure_channel(AUTH) as ach, grpc.insecure_channel(HR) as hch:
        auth=auth_pb2_grpc.AuthServiceStub(ach); hr=hr_pb2_grpc.HRServiceStub(hch)
        admin=auth.Login(auth_pb2.LoginRequest(username=au,password=ap),timeout=5); assert "ADMIN_HOPITAL" in admin.user.roles; amd=md(admin.access_token); ok("Admin login")
        hru=auth.CreateUser(auth_pb2.CreateUserRequest(username=hr_user,password=hr_pass,display_name="HR v2.2 Smoke",roles=["RESPONSABLE_RH"]),metadata=amd,timeout=5).user
        hrl=auth.Login(auth_pb2.LoginRequest(username=hr_user,password=hr_pass),timeout=5); hmd=md(hrl.access_token); assert hrl.dashboard_route=="/ressources-humaines"; ok("HR manager provisioned")
        reg=hr.RegisterEmployee(hr_pb2.RegisterEmployeeRequest(employee_number=empno,first_name="Test",last_name="Employee",email=f"{staff_user}@projectx.test",phone="+25700000000",department="Accueil",job_title="Agent accueil",hire_date=today.isoformat(),employment_type="PERMANENT",username=staff_user,temporary_password=staff_pass),metadata=hmd,timeout=8)
        assert reg.employee.auth_user_id and reg.access_request_status=="PENDING_ADMIN_APPROVAL"; ok("HR employee created + Auth pending account requested")
        expect(grpc.StatusCode.PERMISSION_DENIED,lambda: auth.Login(auth_pb2.LoginRequest(username=staff_user,password=staff_pass),timeout=5),"Pending staff cannot login")
        expect(grpc.StatusCode.PERMISSION_DENIED,lambda: auth.ApproveUser(auth_pb2.ApproveUserRequest(user_id=reg.employee.auth_user_id,role_codes=["AGENT_ACCUEIL"]),metadata=hmd,timeout=5),"HR cannot approve roles")
        approval=auth.ApproveUser(auth_pb2.ApproveUserRequest(user_id=reg.employee.auth_user_id,role_codes=["AGENT_ACCUEIL"]),metadata=amd,timeout=5); qr=approval.qr_payload; assert qr.startswith("PROJECTX-QR1:"); ok("Admin approval + role + QR")
        staff=auth.Login(auth_pb2.LoginRequest(username=staff_user,password=staff_pass),timeout=5); smd=md(staff.access_token); assert staff.dashboard_route=="/accueil"; ok("Credential login -> role dashboard")
        qlogin=auth.LoginWithQr(auth_pb2.QrLoginRequest(qr_payload=qr),timeout=5); assert qlogin.user.id==staff.user.id; ok("QR login")
        shift=hr.CreateShift(hr_pb2.CreateShiftRequest(employee_id=reg.employee.id,shift_date=today.isoformat(),start_time="00:00",end_time="23:59",location="Accueil",idempotency_key=f"shift-{suffix}"),metadata=hmd,timeout=5).shift; ok("HR scheduled employee shift")
        att=hr.ClockIn(hr_pb2.ClockInRequest(note="smoke"),metadata=smd,timeout=5).attendance; assert att.employee_id==reg.employee.id; ok("Employee clock-in")
        hr.ClockOut(hr_pb2.ClockOutRequest(note="smoke"),metadata=smd,timeout=5); ok("Employee clock-out")
        yesterday=today-timedelta(days=1)
        hr.CreateShift(hr_pb2.CreateShiftRequest(employee_id=reg.employee.id,shift_date=yesterday.isoformat(),start_time="08:00",end_time="16:00",location="Accueil",idempotency_key=f"shift-yday-{suffix}"),metadata=hmd,timeout=5)
        finalized=hr.FinalizeAttendanceDay(hr_pb2.FinalizeAttendanceDayRequest(work_date=yesterday.isoformat(),reason="Smoke day close"),metadata=hmd,timeout=5)
        assert finalized.auto_absent_created>=1; ok("HR finalized day and generated absence")
        summary=hr.GetAttendanceSummary(hr_pb2.GetAttendanceSummaryRequest(from_date=yesterday.isoformat(),to_date=today.isoformat(),employee_id=reg.employee.id),metadata=hmd,timeout=5)
        assert summary.absent_days>=1; ok("HR attendance summary")
        leave=hr.SubmitLeaveRequest(hr_pb2.SubmitLeaveRequestRequest(leave_type="ANNUAL",start_date=(today+timedelta(days=10)).isoformat(),end_date=(today+timedelta(days=11)).isoformat(),reason="Smoke test"),metadata=smd,timeout=5).leave_request; ok("Employee leave request")
        reviewed=hr.ReviewLeaveRequest(hr_pb2.ReviewLeaveRequestRequest(leave_request_id=leave.id,decision=hr_pb2.LEAVE_STATUS_APPROVED,review_note="Approved smoke"),metadata=hmd,timeout=5).leave_request; assert reviewed.status==hr_pb2.LEAVE_STATUS_APPROVED; ok("HR reviewed leave")
        dash=hr.GetHrDashboard(hr_pb2.HrDashboardRequest(work_date=today.isoformat()),metadata=hmd,timeout=5); assert dash.active_employees>=1; ok("HR dashboard")
        auth.RevokeQrCredential(auth_pb2.RevokeQrCredentialRequest(user_id=staff.user.id),metadata=amd,timeout=5)
        expect(grpc.StatusCode.UNAUTHENTICATED,lambda: auth.LoginWithQr(auth_pb2.QrLoginRequest(qr_payload=qr),timeout=5),"Revoked QR blocked")
        auth.DisableUser(auth_pb2.DisableUserRequest(user_id=staff.user.id,reason="smoke cleanup"),metadata=amd,timeout=5)
        auth.DisableUser(auth_pb2.DisableUserRequest(user_id=hru.id,reason="smoke cleanup"),metadata=amd,timeout=5)
    print("\nPROJECTX v2.2 HR + AUTH + QR + HR-CONTROLLED ATTENDANCE SMOKE TEST: PASS")
if __name__=="__main__": main()
