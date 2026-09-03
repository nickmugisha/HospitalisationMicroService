from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from services.auth.models import Notification, QrCredential, Role, StaffProfile, User


def _user_options():
    return (
        selectinload(User.roles).selectinload(Role.permissions),
        selectinload(User.qr_credentials),
        selectinload(User.staff_profile),
    )


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).options(*_user_options()).where(User.username == username))


def get_user_by_login_identifier(session: Session, identifier: str) -> User | None:
    value = identifier.strip()
    if not value:
        return None
    # Username remains supported exactly as before. Staff email is an additional login alias.
    statement = (
        select(User)
        .outerjoin(StaffProfile, StaffProfile.user_id == User.id)
        .options(*_user_options())
        .where(or_(User.username == value, func.lower(StaffProfile.email) == value.lower()))
    )
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: str) -> User | None:
    return session.scalar(select(User).options(*_user_options()).where(User.id == user_id))


def get_role_by_code(session: Session, role_code: str) -> Role | None:
    return session.scalar(select(Role).options(selectinload(Role.permissions)).where(Role.code == role_code))


def get_staff_by_employee_number(session: Session, employee_number: str) -> StaffProfile | None:
    return session.scalar(select(StaffProfile).where(StaffProfile.employee_number == employee_number))


def get_staff_by_email(session: Session, email: str) -> StaffProfile | None:
    return session.scalar(select(StaffProfile).where(StaffProfile.email == email))


def get_qr_by_token_hash(session: Session, token_hash: str) -> QrCredential | None:
    return session.scalar(
        select(QrCredential)
        .options(
            selectinload(QrCredential.user).selectinload(User.roles).selectinload(Role.permissions),
            selectinload(QrCredential.user).selectinload(User.qr_credentials),
            selectinload(QrCredential.user).selectinload(User.staff_profile),
        )
        .where(QrCredential.token_hash == token_hash)
    )


def list_users(session: Session, page: int, page_size: int, status: str = "") -> tuple[list[User], int]:
    filters = []
    normalized = status.strip().upper()
    if normalized:
        filters.append(User.approval_status == normalized)
    total = session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    statement = (
        select(User)
        .options(*_user_options())
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.scalars(statement).unique().all()), int(total)


def list_pending_users(session: Session, page: int, page_size: int) -> tuple[list[User], int]:
    return list_users(session, page, page_size, "PENDING_APPROVAL")


def list_active_users_with_role(session: Session, role_code: str) -> list[User]:
    statement = (
        select(User)
        .join(User.roles)
        .options(*_user_options())
        .where(User.active.is_(True), User.approval_status == "ACTIVE", Role.code == role_code, Role.active.is_(True))
        .order_by(User.username.asc())
    )
    return list(session.scalars(statement).unique().all())


def get_notification_by_id(session: Session, notification_id: str) -> Notification | None:
    return session.get(Notification, notification_id)


def collect_user_roles(user: User) -> list[str]:
    return sorted(role.code for role in user.roles if role.active)


def collect_user_permissions(user: User) -> list[str]:
    permissions: set[str] = set()
    for role in user.roles:
        if not role.active:
            continue
        for permission in role.permissions:
            permissions.add(permission.code)
    return sorted(permissions)


def user_has_permission(user: User, permission_code: str) -> bool:
    return permission_code in collect_user_permissions(user)


def list_staff_directory(session: Session, *, role_code: str = "", search: str = "", active_only: bool = True, page: int = 1, page_size: int = 50) -> tuple[list[User], int]:
    statement = select(User).join(StaffProfile, StaffProfile.user_id == User.id)
    count_statement = select(func.count(func.distinct(User.id))).select_from(User).join(StaffProfile, StaffProfile.user_id == User.id)
    filters = []
    if active_only:
        filters.extend([User.active.is_(True), User.approval_status == "ACTIVE"])
    normalized_role = role_code.strip().upper()
    if normalized_role:
        statement = statement.join(User.roles)
        count_statement = count_statement.join(User.roles)
        filters.extend([Role.code == normalized_role, Role.active.is_(True)])
    term = search.strip()
    if term:
        like = f"%{term}%"
        filters.append(or_(
            User.username.like(like), User.display_name.like(like),
            StaffProfile.employee_number.like(like), StaffProfile.department.like(like), StaffProfile.job_title.like(like),
        ))
    total = int(session.scalar(count_statement.where(*filters)) or 0)
    statement = (statement.options(*_user_options()).where(*filters).order_by(User.display_name.asc(), User.username.asc())
                 .offset((page - 1) * page_size).limit(page_size))
    return list(session.scalars(statement).unique().all()), total
