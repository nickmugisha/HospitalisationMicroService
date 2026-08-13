from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import select

from database.session import SessionLocal
from services.auth.models import (
    Permission,
    Role,
    User,
)
from services.auth.rbac import (
    PERMISSIONS,
    ROLES,
    ROLE_PERMISSIONS,
)
from services.auth.security import hash_password


load_dotenv()


def seed_permissions(session):
    result = {}

    for code, name in PERMISSIONS.items():
        permission = session.scalar(
            select(Permission).where(
                Permission.code == code
            )
        )

        if permission is None:
            permission = Permission(
                code=code,
                name=name,
                description=name,
            )

            session.add(permission)
            session.flush()

        result[code] = permission

    return result


def seed_roles(session, permissions):
    result = {}

    for code, data in ROLES.items():
        role = session.scalar(
            select(Role).where(
                Role.code == code
            )
        )

        if role is None:
            role = Role(
                code=code,
                name=data["name"],
                description=data["description"],
                active=True,
            )

            session.add(role)
            session.flush()

        role.permissions = [
            permissions[permission_code]
            for permission_code
            in ROLE_PERMISSIONS.get(code, set())
        ]

        result[code] = role

    return result


def seed_admin(session, roles):
    username = os.getenv(
        "PROJECTX_ADMIN_USERNAME",
        "admin",
    )

    password = os.getenv(
        "PROJECTX_ADMIN_PASSWORD"
    )

    display_name = os.getenv(
        "PROJECTX_ADMIN_DISPLAY_NAME",
        "Administrateur ProjectX",
    )

    if not password:
        raise RuntimeError(
            "PROJECTX_ADMIN_PASSWORD is missing from .env"
        )

    admin = session.scalar(
        select(User).where(
            User.username == username
        )
    )

    if admin is None:
        admin = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            active=True,
        )

        session.add(admin)
        session.flush()

        print(
            f"[CREATE] admin user: {username}"
        )

    else:
        print(
            f"[EXISTS] admin user: {username}"
        )

    admin_role = roles["ADMIN_HOPITAL"]

    if admin_role not in admin.roles:
        admin.roles.append(admin_role)


def main():
    session = SessionLocal()

    try:
        permissions = seed_permissions(
            session
        )

        roles = seed_roles(
            session,
            permissions,
        )

        seed_admin(
            session,
            roles,
        )

        session.commit()

        print()
        print("==============================")
        print(" PROJECTX AUTH SEED COMPLETE")
        print("==============================")
        print(
            f"Permissions : {len(permissions)}"
        )
        print(
            f"Roles       : {len(roles)}"
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()