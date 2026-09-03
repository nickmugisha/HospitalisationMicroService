from __future__ import annotations
import logging
from datetime import date, datetime, time, timedelta, timezone
import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from auth.v1 import auth_pb2, auth_pb2_grpc
from hr.v1 import hr_pb2, hr_pb2_grpc
from database.hr_session import HRSessionLocal, engine
from services.common.auth_guard import require_permission
from services.common.health_compat import build_health_response_compat
from services.common.notifications import send_system_notification
from services.hr.config import AUTH_GRPC_TARGET, HR_LATE_GRACE_MINUTES, HR_LOCAL_UTC_OFFSET_MINUTES, SERVICE_VERSION
from services.hr.models import Attendance, Employee, HRAuditLog, LeaveRequest, Shift, utc_now
from services.hr.repository import get_attendance_day, get_employee, get_employee_by_auth_user, get_employee_by_number, get_leave, get_shift, get_shift_by_idempotency, list_employees

logger = logging.getLogger("projectx.hr.service")

EMPLOYMENT_DB_TO_PROTO = {"ACTIVE": hr_pb2.EMPLOYMENT_STATUS_ACTIVE, "SUSPENDED": hr_pb2.EMPLOYMENT_STATUS_SUSPENDED, "INACTIVE": hr_pb2.EMPLOYMENT_STATUS_INACTIVE, "TERMINATED": hr_pb2.EMPLOYMENT_STATUS_TERMINATED}
EMPLOYMENT_PROTO_TO_DB = {v:k for k,v in EMPLOYMENT_DB_TO_PROTO.items()}
PROVISION_DB_TO_PROTO = {"NOT_PROVISIONED": hr_pb2.ACCOUNT_PROVISION_STATUS_NOT_PROVISIONED, "PROVISIONED_PENDING_ADMIN": hr_pb2.ACCOUNT_PROVISION_STATUS_PROVISIONED_PENDING_ADMIN, "FAILED": hr_pb2.ACCOUNT_PROVISION_STATUS_FAILED}
SHIFT_DB_TO_PROTO = {"SCHEDULED": hr_pb2.SHIFT_STATUS_SCHEDULED, "CANCELLED": hr_pb2.SHIFT_STATUS_CANCELLED, "COMPLETED": hr_pb2.SHIFT_STATUS_COMPLETED}
ATTEND_DB_TO_PROTO = {"PRESENT": hr_pb2.ATTENDANCE_STATUS_PRESENT, "LATE": hr_pb2.ATTENDANCE_STATUS_LATE, "ABSENT": hr_pb2.ATTENDANCE_STATUS_ABSENT, "EXCUSED": hr_pb2.ATTENDANCE_STATUS_EXCUSED}
ATTEND_PROTO_TO_DB = {v:k for k,v in ATTEND_DB_TO_PROTO.items()}
ATTEND_SOURCE_DB_TO_PROTO = {
    "EMPLOYEE_CLOCK": hr_pb2.ATTENDANCE_SOURCE_EMPLOYEE_CLOCK,
    "HR_MANUAL": hr_pb2.ATTENDANCE_SOURCE_HR_MANUAL,
    "SYSTEM_AUTO": hr_pb2.ATTENDANCE_SOURCE_SYSTEM_AUTO,
}
LEAVE_DB_TO_PROTO = {"PENDING": hr_pb2.LEAVE_STATUS_PENDING, "APPROVED": hr_pb2.LEAVE_STATUS_APPROVED, "REJECTED": hr_pb2.LEAVE_STATUS_REJECTED, "CANCELLED": hr_pb2.LEAVE_STATUS_CANCELLED}
LEAVE_PROTO_TO_DB = {v:k for k,v in LEAVE_DB_TO_PROTO.items()}

def ts(value):
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result

def from_ts(value, context, field, required=False):
    if value is None or (value.seconds == 0 and value.nanos == 0):
        if required: context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} is required.")
        return None
    try: return value.ToDatetime(tzinfo=timezone.utc).replace(tzinfo=None)
    except Exception: context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} is invalid.")

def parse_date(value: str, context, field: str, *, required=True):
    raw = value.strip()
    if not raw:
        if required: context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} is required.")
        return None
    try: return date.fromisoformat(raw)
    except ValueError: context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} must use YYYY-MM-DD.")

def parse_time(value: str, context, field: str):
    raw = value.strip()
    if not raw: context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} is required.")
    try: return time.fromisoformat(raw)
    except ValueError: context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} must use HH:MM or HH:MM:SS.")

def local_now():
    return datetime.now(timezone.utc) + timedelta(minutes=HR_LOCAL_UTC_OFFSET_MINUTES)

def auth_metadata(context):
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization": return (("authorization", item.value),)
    return tuple()

def audit(session, context, actor_id, action, resource_type, resource_id=None, outcome="SUCCESS", reason=None):
    session.add(HRAuditLog(actor_auth_user_id=actor_id, action=action, resource_type=resource_type, resource_id=resource_id,
                           outcome=outcome, reason=reason, peer=context.peer() if context else None))

def _as_proto_int(value):
    """Normalize SQL aggregate values (including MySQL Decimal) for protobuf int fields."""
    if value is None:
        return 0
    return int(value)

def employee_to_proto(item: Employee):
    result = hr_pb2.Employee(id=item.id, employee_number=item.employee_number, auth_user_id=item.auth_user_id or "",
        first_name=item.first_name, last_name=item.last_name, email=item.email or "", phone=item.phone or "",
        department=item.department, job_title=item.job_title, hire_date=item.hire_date.isoformat() if item.hire_date else "",
        employment_type=item.employment_type, employment_status=EMPLOYMENT_DB_TO_PROTO.get(item.employment_status, 0),
        account_provision_status=PROVISION_DB_TO_PROTO.get(item.provisioning_status, 0))
    result.created_at.CopyFrom(ts(item.created_at)); result.updated_at.CopyFrom(ts(item.updated_at)); return result

def shift_to_proto(item: Shift):
    result = hr_pb2.Shift(id=item.id, employee_id=item.employee_id, shift_date=item.shift_date.isoformat(),
        start_time=item.start_time.strftime("%H:%M:%S"), end_time=item.end_time.strftime("%H:%M:%S"),
        location=item.location or "", status=SHIFT_DB_TO_PROTO.get(item.status, 0), overnight=(item.end_time <= item.start_time))
    result.created_at.CopyFrom(ts(item.created_at)); return result

def attendance_to_proto(item: Attendance):
    result = hr_pb2.Attendance(id=item.id, employee_id=item.employee_id, work_date=item.work_date.isoformat(),
        status=ATTEND_DB_TO_PROTO.get(item.status, 0), notes=item.notes or "", corrected_by_auth_user_id=item.corrected_by_auth_user_id or "",
        source=ATTEND_SOURCE_DB_TO_PROTO.get(item.source or "EMPLOYEE_CLOCK", 0), late_minutes=item.late_minutes or 0,
        worked_minutes=item.worked_minutes or 0, validated_by_auth_user_id=item.validated_by_auth_user_id or "")
    if item.clock_in_at: result.clock_in_at.CopyFrom(ts(item.clock_in_at))
    if item.clock_out_at: result.clock_out_at.CopyFrom(ts(item.clock_out_at))
    if item.corrected_at: result.corrected_at.CopyFrom(ts(item.corrected_at))
    if item.validated_at: result.validated_at.CopyFrom(ts(item.validated_at))
    return result

def leave_to_proto(item: LeaveRequest):
    result = hr_pb2.LeaveRequest(id=item.id, employee_id=item.employee_id, leave_type=item.leave_type,
        start_date=item.start_date.isoformat(), end_date=item.end_date.isoformat(), reason=item.reason,
        status=LEAVE_DB_TO_PROTO.get(item.status, 0), reviewed_by_auth_user_id=item.reviewed_by_auth_user_id or "",
        review_note=item.review_note or "")
    if item.reviewed_at: result.reviewed_at.CopyFrom(ts(item.reviewed_at))
    result.created_at.CopyFrom(ts(item.created_at)); return result

def shift_bounds_values(shift_date: date, start_time: time, end_time: time):
    start = datetime.combine(shift_date, start_time)
    end = datetime.combine(shift_date, end_time)
    if end_time <= start_time:
        end += timedelta(days=1)
    return start, end


def shift_local_bounds(item: Shift):
    return shift_bounds_values(item.shift_date, item.start_time, item.end_time)


def ensure_no_shift_overlap(session, context, *, employee_id: str, shift_date: date, start_time: time, end_time: time, ignore_shift_id: str = ""):
    proposed_start, proposed_end = shift_bounds_values(shift_date, start_time, end_time)
    candidates = list(session.scalars(select(Shift).where(
        Shift.employee_id == employee_id,
        Shift.status == "SCHEDULED",
        Shift.shift_date >= shift_date - timedelta(days=1),
        Shift.shift_date <= shift_date + timedelta(days=1),
    )).all())
    for other in candidates:
        if ignore_shift_id and other.id == ignore_shift_id:
            continue
        other_start, other_end = shift_local_bounds(other)
        if proposed_start < other_end and proposed_end > other_start:
            context.abort(
                grpc.StatusCode.ALREADY_EXISTS,
                f"Shift overlaps scheduled shift {other.id} ({other_start.isoformat(sep=' ')} -> {other_end.isoformat(sep=' ')}).",
            )


def find_relevant_shift(session, employee_id: str, local_dt: datetime):
    candidates = list(session.scalars(select(Shift).where(
        Shift.employee_id == employee_id, Shift.status == "SCHEDULED",
        Shift.shift_date.in_([local_dt.date(), local_dt.date() - timedelta(days=1)])
    ).order_by(Shift.shift_date, Shift.start_time)).all())
    eligible=[]
    local_naive=local_dt.replace(tzinfo=None)
    for item in candidates:
        start,end=shift_local_bounds(item)
        if start - timedelta(hours=4) <= local_naive <= end + timedelta(hours=6):
            eligible.append((abs((local_naive-start).total_seconds()),item))
    return min(eligible,key=lambda x:x[0])[1] if eligible else None


def audit_to_proto(item: HRAuditLog):
    return hr_pb2.HRAuditLog(
        id=item.id, timestamp=ts(item.timestamp), actor_auth_user_id=item.actor_auth_user_id or "",
        action=item.action, resource_type=item.resource_type, resource_id=item.resource_id or "",
        outcome=item.outcome, reason=item.reason or "", peer=item.peer or "",
    )


def sync_auth_profile(item: Employee, context):
    if not item.auth_user_id:
        return
    with grpc.insecure_channel(AUTH_GRPC_TARGET) as ch:
        auth_pb2_grpc.AuthServiceStub(ch).UpdateStaffProfile(
            auth_pb2.UpdateStaffProfileRequest(
                user_id=item.auth_user_id, first_name=item.first_name, last_name=item.last_name,
                email=item.email or "", phone=item.phone or "", department=item.department, job_title=item.job_title,
            ), metadata=auth_metadata(context), timeout=5)


def sync_auth_employment(item: Employee, reason: str, context):
    if not item.auth_user_id:
        return
    with grpc.insecure_channel(AUTH_GRPC_TARGET) as ch:
        auth_pb2_grpc.AuthServiceStub(ch).SyncStaffEmploymentStatus(
            auth_pb2.SyncStaffEmploymentStatusRequest(user_id=item.auth_user_id,employment_status=item.employment_status,reason=reason),
            metadata=auth_metadata(context),timeout=5)


def best_effort_notify(user_id: str, title: str, body: str, context):
    if not user_id:
        return
    send_system_notification(auth_target=AUTH_GRPC_TARGET,recipient_id=user_id,notification_type="HR",
                             title=title,body=body,source_service="hr")

def provision_auth_account(item: Employee, username: str, password: str, context):
    try:
        with grpc.insecure_channel(AUTH_GRPC_TARGET) as ch:
            response = auth_pb2_grpc.AuthServiceStub(ch).RegisterStaff(
                auth_pb2.RegisterStaffRequest(employee_number=item.employee_number, first_name=item.first_name,
                    last_name=item.last_name, email=item.email or "", phone=item.phone or "", department=item.department,
                    job_title=item.job_title, username=username.strip(), temporary_password=password),
                metadata=auth_metadata(context), timeout=5)
        return response.user.id, None
    except grpc.RpcError as exc:
        return None, f"{exc.code().name}: {exc.details()}"

class HRService(hr_pb2_grpc.HRServiceServicer):
    def RegisterEmployee(self, request, context):
        actor = require_permission(context, "hr.employee.create")
        required = {"employee_number": request.employee_number.strip(), "first_name": request.first_name.strip(),
                    "last_name": request.last_name.strip(), "department": request.department.strip(),
                    "job_title": request.job_title.strip(), "username": request.username.strip(),
                    "temporary_password": request.temporary_password}
        missing = [k for k,v in required.items() if not v]
        if missing: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Missing fields: " + ", ".join(missing))
        if len(required["temporary_password"]) < 8: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Temporary password must have at least 8 characters.")
        hire_date = parse_date(request.hire_date, context, "hire_date", required=False)
        email = request.email.strip().lower() or None
        if email and "@" not in email: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid email.")
        session = HRSessionLocal()
        try:
            existing = get_employee_by_number(session, required["employee_number"])
            if existing is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Employee number already exists.")
            item = Employee(employee_number=required["employee_number"], first_name=required["first_name"], last_name=required["last_name"],
                email=email, phone=request.phone.strip() or None, department=required["department"], job_title=required["job_title"],
                hire_date=hire_date, employment_type=request.employment_type.strip().upper() or "PERMANENT", employment_status="ACTIVE",
                provisioning_status="NOT_PROVISIONED", created_by_auth_user_id=actor.id)
            session.add(item); session.commit(); session.refresh(item)
            auth_user_id, error = provision_auth_account(item, required["username"], required["temporary_password"], context)
            if auth_user_id:
                item.auth_user_id = auth_user_id; item.provisioning_status = "PROVISIONED_PENDING_ADMIN"
                audit(session, context, actor.id, "register_employee", "employee", item.id, reason="Auth account pending admin approval")
                status_text = "PENDING_ADMIN_APPROVAL"
            else:
                item.provisioning_status = "FAILED"
                audit(session, context, actor.id, "register_employee", "employee", item.id, outcome="PARTIAL", reason=error)
                status_text = "HR_SAVED_AUTH_PROVISION_FAILED"
            session.commit(); session.refresh(item)
            return hr_pb2.RegisterEmployeeResponse(employee=employee_to_proto(item), access_request_status=status_text)
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS, "Employee data conflicts with an existing record.")
        finally: session.close()

    def RetryProvisionAccount(self, request, context):
        actor = require_permission(context, "hr.employee.create")
        if not request.username.strip() or len(request.temporary_password) < 8:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Username and temporary password are required.")
        session = HRSessionLocal()
        try:
            item = get_employee(session, request.employee_id.strip(), for_update=True)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Employee not found.")
            if item.auth_user_id:
                return hr_pb2.EmployeeResponse(employee=employee_to_proto(item))
            auth_user_id, error = provision_auth_account(item, request.username, request.temporary_password, context)
            if not auth_user_id:
                item.provisioning_status = "FAILED"; session.commit()
                context.abort(grpc.StatusCode.UNAVAILABLE, "Auth provisioning failed: " + str(error))
            item.auth_user_id = auth_user_id; item.provisioning_status = "PROVISIONED_PENDING_ADMIN"
            audit(session, context, actor.id, "retry_auth_provision", "employee", item.id)
            session.commit(); return hr_pb2.EmployeeResponse(employee=employee_to_proto(item))
        finally: session.close()

    def GetEmployee(self, request, context):
        require_permission(context, "hr.employee.read")
        session = HRSessionLocal()
        try:
            item = get_employee(session, request.employee_id.strip())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Employee not found.")
            return hr_pb2.EmployeeResponse(employee=employee_to_proto(item))
        finally: session.close()

    def ListEmployees(self, request, context):
        require_permission(context, "hr.employee.read")
        session = HRSessionLocal()
        try:
            items,total = list_employees(session, limit=min(max(request.limit or 50,1),200), offset=max(request.offset,0),
                                         department=request.department, status=request.employment_status, search=request.search)
            return hr_pb2.ListEmployeesResponse(employees=[employee_to_proto(x) for x in items], total=total)
        finally: session.close()

    def UpdateEmployee(self, request, context):
        actor = require_permission(context, "hr.employee.update")
        session = HRSessionLocal()
        try:
            item = get_employee(session, request.employee_id.strip(), for_update=True)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Employee not found.")
            if request.first_name.strip(): item.first_name = request.first_name.strip()
            if request.last_name.strip(): item.last_name = request.last_name.strip()
            if request.email.strip(): item.email = request.email.strip().lower()
            if request.phone.strip(): item.phone = request.phone.strip()
            if request.department.strip(): item.department = request.department.strip()
            if request.job_title.strip(): item.job_title = request.job_title.strip()
            if request.employment_type.strip(): item.employment_type = request.employment_type.strip().upper()
            audit(session, context, actor.id, "update_employee", "employee", item.id)
            session.commit(); session.refresh(item)
            try:
                sync_auth_profile(item, context)
            except grpc.RpcError as exc:
                audit(session,context,actor.id,"sync_auth_profile","employee",item.id,outcome="PARTIAL",reason=f"{exc.code().name}: {exc.details()}")
                session.commit()
                context.abort(grpc.StatusCode.UNAVAILABLE,"Employee saved but Auth profile synchronization failed.")
            return hr_pb2.EmployeeResponse(employee=employee_to_proto(item))
        finally: session.close()

    def SetEmploymentStatus(self, request, context):
        actor = require_permission(context, "hr.employee.status")
        status = EMPLOYMENT_PROTO_TO_DB.get(request.status)
        if not status: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "A valid employment status is required.")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Reason is required for employment status change.")
        session = HRSessionLocal()
        try:
            item = get_employee(session, request.employee_id.strip(), for_update=True)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Employee not found.")
            item.employment_status = status
            audit(session, context, actor.id, "set_employment_status", "employee", item.id, reason=request.reason.strip())
            session.commit(); session.refresh(item)
            try:
                sync_auth_employment(item, request.reason.strip(), context)
            except grpc.RpcError as exc:
                audit(session,context,actor.id,"sync_auth_employment","employee",item.id,outcome="PARTIAL",reason=f"{exc.code().name}: {exc.details()}")
                session.commit()
                context.abort(grpc.StatusCode.UNAVAILABLE,"Employment status saved but Auth access synchronization failed.")
            return hr_pb2.EmployeeResponse(employee=employee_to_proto(item))
        finally: session.close()

    def CreateShift(self, request, context):
        actor = require_permission(context, "hr.shift.manage")
        shift_date = parse_date(request.shift_date, context, "shift_date")
        start = parse_time(request.start_time, context, "start_time"); end = parse_time(request.end_time, context, "end_time")
        key = request.idempotency_key.strip()
        if not key: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "idempotency_key is required.")
        if end == start: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "start_time and end_time cannot be equal.")
        session = HRSessionLocal()
        try:
            existing = get_shift_by_idempotency(session, key)
            if existing: return hr_pb2.ShiftResponse(shift=shift_to_proto(existing))
            employee = get_employee(session, request.employee_id.strip())
            if employee is None: context.abort(grpc.StatusCode.NOT_FOUND, "Employee not found.")
            if employee.employment_status != "ACTIVE": context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only active employees can receive shifts.")
            ensure_no_shift_overlap(session, context, employee_id=employee.id, shift_date=shift_date, start_time=start, end_time=end)
            item = Shift(employee_id=employee.id, shift_date=shift_date, start_time=start, end_time=end, location=request.location.strip() or None,
                         status="SCHEDULED", idempotency_key=key, created_by_auth_user_id=actor.id)
            session.add(item); audit(session, context, actor.id, "create_shift", "shift", item.id)
            session.commit(); session.refresh(item); return hr_pb2.ShiftResponse(shift=shift_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS, "Overlapping/duplicate shift key or start already exists.")
        finally: session.close()

    def UpdateShift(self, request, context):
        actor=require_permission(context,"hr.shift.manage")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"reason is required.")
        shift_date=parse_date(request.shift_date,context,"shift_date")
        start=parse_time(request.start_time,context,"start_time"); end=parse_time(request.end_time,context,"end_time")
        if end==start: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"start_time and end_time cannot be equal.")
        session=HRSessionLocal()
        try:
            item=get_shift(session,request.shift_id.strip(),for_update=True)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Shift not found.")
            if item.status!="SCHEDULED": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only a scheduled shift can be updated.")
            if get_attendance_day(session,item.employee_id,item.shift_date) is not None:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Cannot change a shift after attendance exists for its work date.")
            if shift_date != item.shift_date and get_attendance_day(session,item.employee_id,shift_date) is not None:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Cannot move a shift onto a work date that already has attendance.")
            ensure_no_shift_overlap(session, context, employee_id=item.employee_id, shift_date=shift_date, start_time=start, end_time=end, ignore_shift_id=item.id)
            item.shift_date=shift_date; item.start_time=start; item.end_time=end; item.location=request.location.strip() or None
            audit(session,context,actor.id,"update_shift","shift",item.id,reason=request.reason.strip())
            session.commit(); session.refresh(item); return hr_pb2.ShiftResponse(shift=shift_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS,"Updated shift conflicts with another shift.")
        finally: session.close()

    def ListShifts(self, request, context):
        require_permission(context, "hr.shift.read")
        filters=[]
        if request.employee_id.strip(): filters.append(Shift.employee_id == request.employee_id.strip())
        if request.from_date.strip(): filters.append(Shift.shift_date >= parse_date(request.from_date, context, "from_date"))
        if request.to_date.strip(): filters.append(Shift.shift_date <= parse_date(request.to_date, context, "to_date"))
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=HRSessionLocal()
        try:
            total=_as_proto_int(session.scalar(select(func.count()).select_from(Shift).where(*filters)))
            items=list(session.scalars(select(Shift).where(*filters).order_by(Shift.shift_date, Shift.start_time).offset(offset).limit(limit)).all())
            return hr_pb2.ListShiftsResponse(shifts=[shift_to_proto(x) for x in items], total=total)
        finally: session.close()

    def CancelShift(self, request, context):
        actor=require_permission(context,"hr.shift.manage")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Cancellation reason is required.")
        session=HRSessionLocal()
        try:
            item=get_shift(session,request.shift_id.strip(),for_update=True)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Shift not found.")
            if item.status=="CANCELLED": return hr_pb2.ShiftResponse(shift=shift_to_proto(item))
            if item.status!="SCHEDULED": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only scheduled shifts can be cancelled.")
            item.status="CANCELLED"; audit(session,context,actor.id,"cancel_shift","shift",item.id,reason=request.reason.strip())
            session.commit(); return hr_pb2.ShiftResponse(shift=shift_to_proto(item))
        finally: session.close()

    def ClockIn(self, request, context):
        actor=require_permission(context,"hr.attendance.clock")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            if employee.employment_status!="ACTIVE": context.abort(grpc.StatusCode.PERMISSION_DENIED,"Employment is not active.")
            local=local_now(); now=utc_now(); shift=find_relevant_shift(session,employee.id,local)
            work_date=shift.shift_date if shift else local.date()
            existing=get_attendance_day(session,employee.id,work_date,for_update=True)
            if existing and existing.clock_in_at: context.abort(grpc.StatusCode.ALREADY_EXISTS,"Employee already clocked in for this work date.")
            status="PRESENT"; late_minutes=0
            if shift:
                shift_start,_=shift_local_bounds(shift); arrival_local=local.replace(tzinfo=None)
                if arrival_local > shift_start + timedelta(minutes=HR_LATE_GRACE_MINUTES):
                    status="LATE"; late_minutes=max(0,int((arrival_local-shift_start).total_seconds()//60))
            item=existing or Attendance(employee_id=employee.id,work_date=work_date)
            item.clock_in_at=now; item.status=status; item.source="EMPLOYEE_CLOCK"; item.late_minutes=late_minutes
            if request.note.strip(): item.notes=request.note.strip()
            if existing is None: session.add(item)
            audit(session,context,actor.id,"clock_in","attendance",item.id)
            session.commit(); session.refresh(item); return hr_pb2.AttendanceResponse(attendance=attendance_to_proto(item))
        finally: session.close()

    def ClockOut(self, request, context):
        actor=require_permission(context,"hr.attendance.clock")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            item=session.scalar(select(Attendance).where(Attendance.employee_id==employee.id,Attendance.clock_in_at.is_not(None),Attendance.clock_out_at.is_(None)).order_by(Attendance.clock_in_at.desc()).with_for_update())
            if item is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Clock in before clock out.")
            item.clock_out_at=utc_now(); item.worked_minutes=max(0,int((item.clock_out_at-item.clock_in_at).total_seconds()//60))
            if request.note.strip(): item.notes=((item.notes+" | ") if item.notes else "")+request.note.strip()
            audit(session,context,actor.id,"clock_out","attendance",item.id)
            session.commit(); return hr_pb2.AttendanceResponse(attendance=attendance_to_proto(item))
        finally: session.close()

    def GetMyAttendanceToday(self, request, context):
        actor=require_permission(context,"hr.self.read")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            local=local_now(); shift=find_relevant_shift(session,employee.id,local); work_date=shift.shift_date if shift else local.date()
            item=get_attendance_day(session,employee.id,work_date)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"No attendance record exists for the current work date.")
            return hr_pb2.AttendanceResponse(attendance=attendance_to_proto(item))
        finally: session.close()

    def ListMyAttendance(self, request, context):
        actor=require_permission(context,"hr.self.read")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            filters=[Attendance.employee_id==employee.id]
            if request.from_date.strip(): filters.append(Attendance.work_date>=parse_date(request.from_date,context,"from_date"))
            if request.to_date.strip(): filters.append(Attendance.work_date<=parse_date(request.to_date,context,"to_date"))
            limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
            total=_as_proto_int(session.scalar(select(func.count()).select_from(Attendance).where(*filters)))
            items=list(session.scalars(select(Attendance).where(*filters).order_by(Attendance.work_date.desc()).offset(offset).limit(limit)).all())
            return hr_pb2.ListAttendanceResponse(attendance=[attendance_to_proto(x) for x in items],total=total)
        finally: session.close()

    def ListMyShifts(self, request, context):
        actor=require_permission(context,"hr.self.read")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            filters=[Shift.employee_id==employee.id]
            if request.from_date.strip(): filters.append(Shift.shift_date>=parse_date(request.from_date,context,"from_date"))
            if request.to_date.strip(): filters.append(Shift.shift_date<=parse_date(request.to_date,context,"to_date"))
            limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
            total=_as_proto_int(session.scalar(select(func.count()).select_from(Shift).where(*filters)))
            items=list(session.scalars(select(Shift).where(*filters).order_by(Shift.shift_date,Shift.start_time).offset(offset).limit(limit)).all())
            return hr_pb2.ListShiftsResponse(shifts=[shift_to_proto(x) for x in items],total=total)
        finally: session.close()

    def RecordAttendanceByHR(self, request, context):
        actor=require_permission(context,"hr.attendance.manage")
        work_date=parse_date(request.work_date,context,"work_date")
        if work_date > local_now().date(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Cannot record attendance for a future date.")
        status=ATTEND_PROTO_TO_DB.get(request.status)
        if not status: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"A valid attendance status is required.")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"HR reason is required.")
        clock_in=from_ts(request.clock_in_at,context,"clock_in_at",required=False) if request.HasField("clock_in_at") else None
        clock_out=from_ts(request.clock_out_at,context,"clock_out_at",required=False) if request.HasField("clock_out_at") else None
        if clock_out and clock_in and clock_out < clock_in: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"clock_out_at cannot be before clock_in_at.")
        if status in {"PRESENT","LATE"} and clock_in is None:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"PRESENT/LATE attendance requires clock_in_at.")
        session=HRSessionLocal()
        try:
            employee=get_employee(session,request.employee_id.strip())
            if employee is None: context.abort(grpc.StatusCode.NOT_FOUND,"Employee not found.")
            item=get_attendance_day(session,employee.id,work_date,for_update=True)
            if item is None:
                item=Attendance(employee_id=employee.id,work_date=work_date); session.add(item)
            item.clock_in_at=clock_in; item.clock_out_at=clock_out; item.status=status; item.notes=request.reason.strip(); item.source="HR_MANUAL"
            item.worked_minutes=max(0,int((clock_out-clock_in).total_seconds()//60)) if clock_in and clock_out else 0
            item.late_minutes=0
            shift=session.scalar(select(Shift).where(Shift.employee_id==employee.id,Shift.shift_date==work_date,Shift.status=="SCHEDULED").order_by(Shift.start_time).limit(1))
            if clock_in and shift:
                local_clock_in=clock_in + timedelta(minutes=HR_LOCAL_UTC_OFFSET_MINUTES)
                shift_start=datetime.combine(work_date,shift.start_time)
                item.late_minutes=max(0,int((local_clock_in-shift_start).total_seconds()//60))
            item.validated_by_auth_user_id=actor.id; item.validated_at=utc_now()
            audit(session,context,actor.id,"record_attendance_by_hr","attendance",item.id,reason=request.reason.strip())
            session.commit(); session.refresh(item); return hr_pb2.AttendanceResponse(attendance=attendance_to_proto(item))
        finally: session.close()

    def FinalizeAttendanceDay(self, request, context):
        actor=require_permission(context,"hr.attendance.close_day")
        work_date=parse_date(request.work_date,context,"work_date")
        if work_date > local_now().date(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Cannot finalize a future attendance day.")
        reason=request.reason.strip() or "HR attendance day finalization"
        session=HRSessionLocal()
        try:
            scheduled=list(session.scalars(select(Shift).where(Shift.shift_date==work_date,Shift.status=="SCHEDULED")).all())
            now_local=local_now().replace(tzinfo=None)
            not_finished=[shift for shift in scheduled if shift_local_bounds(shift)[1] > now_local]
            if not_finished:
                latest=max(shift_local_bounds(x)[1] for x in not_finished)
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,f"Cannot finalize attendance before all scheduled shifts end. Latest end: {latest.isoformat(sep=' ')}")
            existing=0; absent_created=0; excused_created=0
            for shift in scheduled:
                item=get_attendance_day(session,shift.employee_id,work_date,for_update=True)
                if item is not None:
                    existing+=1
                    if item.validated_at is None:
                        item.validated_by_auth_user_id=actor.id; item.validated_at=utc_now()
                    continue
                leave=session.scalar(select(LeaveRequest).where(LeaveRequest.employee_id==shift.employee_id,LeaveRequest.status=="APPROVED",LeaveRequest.start_date<=work_date,LeaveRequest.end_date>=work_date).limit(1))
                status="EXCUSED" if leave else "ABSENT"
                note=f"{reason}; approved leave" if leave else reason
                item=Attendance(employee_id=shift.employee_id,work_date=work_date,status=status,notes=note,source="SYSTEM_AUTO",validated_by_auth_user_id=actor.id,validated_at=utc_now())
                session.add(item)
                if leave: excused_created+=1
                else: absent_created+=1
            audit(session,context,actor.id,"finalize_attendance_day","attendance_day",work_date.isoformat(),reason=reason)
            session.commit()
            return hr_pb2.FinalizeAttendanceDayResponse(work_date=work_date.isoformat(),scheduled_employees=len(scheduled),existing_records=existing,auto_absent_created=absent_created,auto_excused_created=excused_created)
        finally: session.close()

    def CorrectAttendance(self, request, context):
        actor=require_permission(context,"hr.attendance.correct")
        work_date=parse_date(request.work_date,context,"work_date")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Correction reason is required.")
        status=ATTEND_PROTO_TO_DB.get(request.status)
        if not status: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"A valid attendance status is required.")
        clock_in=from_ts(request.clock_in_at,context,"clock_in_at",required=False) if request.HasField("clock_in_at") else None
        clock_out=from_ts(request.clock_out_at,context,"clock_out_at",required=False) if request.HasField("clock_out_at") else None
        if clock_out and clock_in and clock_out < clock_in: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"clock_out_at cannot be before clock_in_at.")
        session=HRSessionLocal()
        try:
            employee=get_employee(session,request.employee_id.strip())
            if employee is None: context.abort(grpc.StatusCode.NOT_FOUND,"Employee not found.")
            item=get_attendance_day(session,employee.id,work_date,for_update=True)
            if item is None:
                item=Attendance(employee_id=employee.id,work_date=work_date); session.add(item)
            item.clock_in_at=clock_in; item.clock_out_at=clock_out; item.status=status; item.notes=request.reason.strip()
            item.source="HR_MANUAL"
            item.worked_minutes=max(0, int((clock_out-clock_in).total_seconds()//60)) if clock_in and clock_out else 0
            item.late_minutes=0
            shift=session.scalar(select(Shift).where(Shift.employee_id==employee.id,Shift.shift_date==work_date,Shift.status=="SCHEDULED").order_by(Shift.start_time).limit(1))
            if clock_in and shift:
                local_clock_in=clock_in + timedelta(minutes=HR_LOCAL_UTC_OFFSET_MINUTES)
                shift_start=datetime.combine(work_date,shift.start_time)
                item.late_minutes=max(0,int((local_clock_in-shift_start).total_seconds()//60))
            item.corrected_by_auth_user_id=actor.id; item.corrected_at=utc_now()
            item.validated_by_auth_user_id=actor.id; item.validated_at=utc_now()
            audit(session,context,actor.id,"correct_attendance","attendance",item.id,reason=request.reason.strip())
            session.commit(); session.refresh(item); return hr_pb2.AttendanceResponse(attendance=attendance_to_proto(item))
        finally: session.close()

    def ListAttendance(self, request, context):
        require_permission(context,"hr.attendance.read")
        filters=[]
        if request.employee_id.strip(): filters.append(Attendance.employee_id==request.employee_id.strip())
        if request.from_date.strip(): filters.append(Attendance.work_date>=parse_date(request.from_date,context,"from_date"))
        if request.to_date.strip(): filters.append(Attendance.work_date<=parse_date(request.to_date,context,"to_date"))
        if request.status.strip(): filters.append(Attendance.status==request.status.strip().upper())
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=HRSessionLocal()
        try:
            total=_as_proto_int(session.scalar(select(func.count()).select_from(Attendance).where(*filters)))
            items=list(session.scalars(select(Attendance).where(*filters).order_by(Attendance.work_date.desc()).offset(offset).limit(limit)).all())
            return hr_pb2.ListAttendanceResponse(attendance=[attendance_to_proto(x) for x in items],total=total)
        finally: session.close()

    def GetAttendanceSummary(self, request, context):
        require_permission(context,"hr.attendance.summary")
        from_date=parse_date(request.from_date,context,"from_date")
        to_date=parse_date(request.to_date,context,"to_date")
        if to_date < from_date: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"to_date cannot be before from_date.")
        filters=[Attendance.work_date>=from_date,Attendance.work_date<=to_date]
        if request.employee_id.strip(): filters.append(Attendance.employee_id==request.employee_id.strip())
        session=HRSessionLocal()
        try:
            stmt=select(Attendance).join(Employee,Employee.id==Attendance.employee_id).where(*filters)
            if request.department.strip(): stmt=stmt.where(Employee.department==request.department.strip())
            items=list(session.scalars(stmt.order_by(Attendance.employee_id,Attendance.work_date)).all())
            employee_ids=sorted({x.employee_id for x in items})
            employees={x.id:x for x in session.scalars(select(Employee).where(Employee.id.in_(employee_ids))).all()} if employee_ids else {}
            grouped={}
            totals={"PRESENT":0,"LATE":0,"ABSENT":0,"EXCUSED":0,"late":0,"worked":0}
            for item in items:
                g=grouped.setdefault(item.employee_id,{"PRESENT":0,"LATE":0,"ABSENT":0,"EXCUSED":0,"late":0,"worked":0})
                if item.status in g: g[item.status]+=1
                if item.status in totals: totals[item.status]+=1
                g["late"]+=item.late_minutes or 0; g["worked"]+=item.worked_minutes or 0
                totals["late"]+=item.late_minutes or 0; totals["worked"]+=item.worked_minutes or 0
            rows=[]
            for employee_id,g in grouped.items():
                e=employees.get(employee_id)
                rows.append(hr_pb2.AttendanceEmployeeSummary(employee_id=employee_id,employee_number=e.employee_number if e else "",display_name=(f"{e.first_name} {e.last_name}".strip() if e else ""),department=e.department if e else "",present_days=g["PRESENT"],late_days=g["LATE"],absent_days=g["ABSENT"],excused_days=g["EXCUSED"],late_minutes=g["late"],worked_minutes=g["worked"]))
            return hr_pb2.AttendanceSummaryResponse(from_date=from_date.isoformat(),to_date=to_date.isoformat(),present_days=totals["PRESENT"],late_days=totals["LATE"],absent_days=totals["ABSENT"],excused_days=totals["EXCUSED"],total_late_minutes=totals["late"],total_worked_minutes=totals["worked"],employees=rows)
        finally: session.close()

    def SubmitLeaveRequest(self, request, context):
        actor=require_permission(context,"hr.leave.submit")
        start=parse_date(request.start_date,context,"start_date"); end=parse_date(request.end_date,context,"end_date")
        if end<start: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"end_date cannot be before start_date.")
        if not request.leave_type.strip() or not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"leave_type and reason are required.")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            overlap=session.scalar(select(LeaveRequest).where(LeaveRequest.employee_id==employee.id,LeaveRequest.status.in_(["PENDING","APPROVED"]),LeaveRequest.start_date<=end,LeaveRequest.end_date>=start).limit(1))
            if overlap: context.abort(grpc.StatusCode.ALREADY_EXISTS,"An overlapping leave request already exists.")
            item=LeaveRequest(employee_id=employee.id,leave_type=request.leave_type.strip().upper(),start_date=start,end_date=end,reason=request.reason.strip(),status="PENDING")
            session.add(item); audit(session,context,actor.id,"submit_leave","leave_request",item.id)
            session.commit(); session.refresh(item); return hr_pb2.LeaveRequestResponse(leave_request=leave_to_proto(item))
        finally: session.close()

    def ReviewLeaveRequest(self, request, context):
        actor=require_permission(context,"hr.leave.review")
        decision=LEAVE_PROTO_TO_DB.get(request.decision)
        if decision not in {"APPROVED","REJECTED"}: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Decision must be APPROVED or REJECTED.")
        session=HRSessionLocal()
        try:
            item=get_leave(session,request.leave_request_id.strip(),for_update=True)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Leave request not found.")
            if item.status!="PENDING": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only pending leave requests can be reviewed.")
            item.status=decision; item.reviewed_by_auth_user_id=actor.id; item.reviewed_at=utc_now(); item.review_note=request.review_note.strip() or None
            employee=get_employee(session,item.employee_id)
            audit(session,context,actor.id,"review_leave","leave_request",item.id,reason=decision)
            session.commit()
            if employee and employee.auth_user_id: best_effort_notify(employee.auth_user_id,"Décision de congé",f"Votre demande de congé est {decision}.",context)
            return hr_pb2.LeaveRequestResponse(leave_request=leave_to_proto(item))
        finally: session.close()

    def ListLeaveRequests(self, request, context):
        require_permission(context,"hr.leave.read")
        filters=[]
        if request.employee_id.strip(): filters.append(LeaveRequest.employee_id==request.employee_id.strip())
        if request.status.strip(): filters.append(LeaveRequest.status==request.status.strip().upper())
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=HRSessionLocal()
        try:
            total=_as_proto_int(session.scalar(select(func.count()).select_from(LeaveRequest).where(*filters)))
            items=list(session.scalars(select(LeaveRequest).where(*filters).order_by(LeaveRequest.created_at.desc()).offset(offset).limit(limit)).all())
            return hr_pb2.ListLeaveRequestsResponse(leave_requests=[leave_to_proto(x) for x in items],total=total)
        finally: session.close()

    def ListMyLeaveRequests(self, request, context):
        actor=require_permission(context,"hr.self.read")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            filters=[LeaveRequest.employee_id==employee.id]
            if request.status.strip(): filters.append(LeaveRequest.status==request.status.strip().upper())
            limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
            total=_as_proto_int(session.scalar(select(func.count()).select_from(LeaveRequest).where(*filters)))
            items=list(session.scalars(select(LeaveRequest).where(*filters).order_by(LeaveRequest.created_at.desc()).offset(offset).limit(limit)).all())
            return hr_pb2.ListLeaveRequestsResponse(leave_requests=[leave_to_proto(x) for x in items],total=total)
        finally: session.close()

    def CancelMyLeaveRequest(self, request, context):
        actor=require_permission(context,"hr.self.read")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Cancellation reason is required.")
        session=HRSessionLocal()
        try:
            employee=get_employee_by_auth_user(session,actor.id)
            if employee is None: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"No HR employee profile is linked to this account.")
            item=get_leave(session,request.leave_request_id.strip(),for_update=True)
            if item is None or item.employee_id!=employee.id: context.abort(grpc.StatusCode.NOT_FOUND,"Leave request not found.")
            if item.status!="PENDING": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only a pending leave request can be cancelled by its owner.")
            item.status="CANCELLED"; item.review_note=request.reason.strip(); item.updated_at=utc_now()
            audit(session,context,actor.id,"cancel_own_leave","leave_request",item.id,reason=request.reason.strip())
            session.commit(); return hr_pb2.LeaveRequestResponse(leave_request=leave_to_proto(item))
        finally: session.close()

    def GetHrDashboard(self, request, context):
        require_permission(context,"hr.dashboard.read")
        work_date=parse_date(request.work_date,context,"work_date",required=False) or local_now().date()
        session=HRSessionLocal()
        try:
            active=_as_proto_int(session.scalar(select(func.count()).select_from(Employee).where(Employee.employment_status=="ACTIVE")))
            shifts=list(session.scalars(select(Shift).where(Shift.shift_date==work_date,Shift.status=="SCHEDULED")).all())
            scheduled=len(shifts)
            present=_as_proto_int(session.scalar(select(func.count()).select_from(Attendance).where(Attendance.work_date==work_date,Attendance.status=="PRESENT")))
            late=_as_proto_int(session.scalar(select(func.count()).select_from(Attendance).where(Attendance.work_date==work_date,Attendance.status=="LATE")))
            excused=_as_proto_int(session.scalar(select(func.count()).select_from(Attendance).where(Attendance.work_date==work_date,Attendance.status=="EXCUSED")))
            late_minutes=_as_proto_int(session.scalar(select(func.coalesce(func.sum(Attendance.late_minutes),0)).where(Attendance.work_date==work_date)))
            worked_minutes=_as_proto_int(session.scalar(select(func.coalesce(func.sum(Attendance.worked_minutes),0)).where(Attendance.work_date==work_date)))
            records={x.employee_id:x for x in session.scalars(select(Attendance).where(Attendance.work_date==work_date)).all()}
            now_local=local_now().replace(tzinfo=None); absent=0; not_started=0
            for shift in shifts:
                record=records.get(shift.employee_id)
                if record is not None:
                    if record.status=="ABSENT": absent+=1
                    continue
                _,end_local=shift_local_bounds(shift)
                if end_local <= now_local: absent+=1
                else: not_started+=1
            pending=_as_proto_int(session.scalar(select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status=="PENDING")))
            return hr_pb2.HrDashboardResponse(work_date=work_date.isoformat(),active_employees=active,scheduled_today=scheduled,
                present_today=present,late_today=late,absent_today=absent,pending_leave_requests=pending,
                excused_today=excused,total_late_minutes_today=late_minutes,total_worked_minutes_today=worked_minutes,not_started_today=not_started)
        finally: session.close()

    def ListHrAuditLogs(self, request, context):
        require_permission(context,"hr.audit.read")
        filters=[]
        if request.actor_auth_user_id.strip(): filters.append(HRAuditLog.actor_auth_user_id==request.actor_auth_user_id.strip())
        if request.action.strip(): filters.append(HRAuditLog.action==request.action.strip())
        if request.resource_type.strip(): filters.append(HRAuditLog.resource_type==request.resource_type.strip())
        if request.resource_id.strip(): filters.append(HRAuditLog.resource_id==request.resource_id.strip())
        if request.from_date.strip(): filters.append(HRAuditLog.timestamp>=datetime.combine(parse_date(request.from_date,context,"from_date"),time.min))
        if request.to_date.strip(): filters.append(HRAuditLog.timestamp<datetime.combine(parse_date(request.to_date,context,"to_date")+timedelta(days=1),time.min))
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=HRSessionLocal()
        try:
            total=_as_proto_int(session.scalar(select(func.count()).select_from(HRAuditLog).where(*filters)))
            items=list(session.scalars(select(HRAuditLog).where(*filters).order_by(HRAuditLog.timestamp.desc()).offset(offset).limit(limit)).all())
            return hr_pb2.ListHrAuditLogsResponse(logs=[audit_to_proto(x) for x in items],total=total)
        finally: session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection: connection.execute(text("SELECT 1"))
            return build_health_response_compat("hr","ONLINE","HR service and MySQL are available.",SERVICE_VERSION)
        except Exception:
            logger.exception("HR health degraded")
            return build_health_response_compat("hr","DEGRADED","HR service is running but MySQL is unavailable.",SERVICE_VERSION)
