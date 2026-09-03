from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.hr_base import HRBase

def uid(): return str(uuid.uuid4())
def utc_now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class Employee(HRBase):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    employee_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    auth_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String(120), nullable=False)
    hire_date: Mapped[object | None] = mapped_column(Date(), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(40), nullable=False, default="PERMANENT")
    employment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)
    provisioning_status: Mapped[str] = mapped_column(String(40), nullable=False, default="NOT_PROVISIONED")
    created_by_auth_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    shifts: Mapped[list["Shift"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(back_populates="employee", cascade="all, delete-orphan")

class Shift(HRBase):
    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("employee_id", "shift_date", "start_time", name="uq_hr_employee_shift_start"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_date: Mapped[object] = mapped_column(Date(), nullable=False, index=True)
    start_time: Mapped[object] = mapped_column(Time(), nullable=False)
    end_time: Mapped[object] = mapped_column(Time(), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED")
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_by_auth_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    employee: Mapped[Employee] = relationship(back_populates="shifts")

class Attendance(HRBase):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_hr_attendance_employee_day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[object] = mapped_column(Date(), nullable=False, index=True)
    clock_in_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PRESENT", index=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    corrected_by_auth_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="EMPLOYEE_CLOCK", index=True)
    late_minutes: Mapped[int] = mapped_column(nullable=False, default=0)
    worked_minutes: Mapped[int] = mapped_column(nullable=False, default=0)
    validated_by_auth_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    employee: Mapped[Employee] = relationship(back_populates="attendance")

class LeaveRequest(HRBase):
    __tablename__ = "leave_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[object] = mapped_column(Date(), nullable=False)
    end_date: Mapped[object] = mapped_column(Date(), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    reviewed_by_auth_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    employee: Mapped[Employee] = relationship(back_populates="leave_requests")

class HRAuditLog(HRBase):
    __tablename__ = "hr_audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    actor_auth_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCESS")
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    peer: Mapped[str | None] = mapped_column(String(255), nullable=True)
