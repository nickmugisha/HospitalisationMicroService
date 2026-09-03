from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from services.hr.models import Attendance, Employee, LeaveRequest, Shift

def get_employee(session: Session, employee_id: str, *, for_update=False):
    stmt = select(Employee).where(Employee.id == employee_id)
    if for_update: stmt = stmt.with_for_update()
    return session.scalar(stmt)

def get_employee_by_number(session: Session, number: str):
    return session.scalar(select(Employee).where(Employee.employee_number == number))

def get_employee_by_auth_user(session: Session, user_id: str):
    return session.scalar(select(Employee).where(Employee.auth_user_id == user_id))

def list_employees(session: Session, *, limit=50, offset=0, department="", status="", search=""):
    filters = []
    if department.strip(): filters.append(Employee.department == department.strip())
    if status.strip(): filters.append(Employee.employment_status == status.strip().upper())
    if search.strip():
        term = f"%{search.strip()}%"
        filters.append(or_(Employee.employee_number.like(term), Employee.first_name.like(term), Employee.last_name.like(term), Employee.job_title.like(term)))
    total = session.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
    items = list(session.scalars(select(Employee).where(*filters).order_by(Employee.last_name, Employee.first_name).offset(offset).limit(limit)).all())
    return items, total

def get_shift(session: Session, shift_id: str, *, for_update=False):
    stmt = select(Shift).where(Shift.id == shift_id)
    if for_update: stmt = stmt.with_for_update()
    return session.scalar(stmt)

def get_shift_by_idempotency(session: Session, key: str):
    return session.scalar(select(Shift).where(Shift.idempotency_key == key))

def get_attendance_day(session: Session, employee_id: str, work_date, *, for_update=False):
    stmt = select(Attendance).where(Attendance.employee_id == employee_id, Attendance.work_date == work_date)
    if for_update: stmt = stmt.with_for_update()
    return session.scalar(stmt)

def get_leave(session: Session, leave_id: str, *, for_update=False):
    stmt = select(LeaveRequest).where(LeaveRequest.id == leave_id)
    if for_update: stmt = stmt.with_for_update()
    return session.scalar(stmt)
