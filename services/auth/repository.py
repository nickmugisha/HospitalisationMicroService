from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from services.auth.models import (
    Permission,
    Role,
    User,
)


def get_user_by_username(
    session: Session,
    username: str,
) -> User | None:
    statement = (
        select(User)
        .options(
            selectinload(User.roles)
            .selectinload(Role.permissions)
        )
        .where(
            User.username == username
        )
    )

    return session.scalar(statement)


def get_user_by_id(
    session: Session,
    user_id: str,
) -> User | None:
    statement = (
        select(User)
        .options(
            selectinload(User.roles)
            .selectinload(Role.permissions)
        )
        .where(
            User.id == user_id
        )
    )

    return session.scalar(statement)


def get_role_by_code(
    session: Session,
    role_code: str,
) -> Role | None:
    statement = (
        select(Role)
        .options(
            selectinload(Role.permissions)
        )
        .where(
            Role.code == role_code
        )
    )

    return session.scalar(statement)


def get_permission_by_code(
    session: Session,
    permission_code: str,
) -> Permission | None:
    return session.scalar(
        select(Permission).where(
            Permission.code
            == permission_code
        )
    )


def collect_user_roles(
    user: User,
) -> list[str]:
    return sorted(
        role.code
        for role in user.roles
        if role.active
    )


def collect_user_permissions(
    user: User,
) -> list[str]:
    permissions: set[str] = set()

    for role in user.roles:
        if not role.active:
            continue

        for permission in role.permissions:
            permissions.add(
                permission.code
            )

    return sorted(permissions)


def user_has_permission(
    user: User,
    permission_code: str,
) -> bool:
    return (
        permission_code
        in collect_user_permissions(user)
    )