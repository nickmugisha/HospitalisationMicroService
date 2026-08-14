from services.auth.repository import (
    collect_user_permissions,
    collect_user_roles,
    get_user_by_username,
)
from services.auth.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from database.session import SessionLocal

import getpass


def main():
    username = input("Username: ").strip()

    password = getpass.getpass(
        "Password: "
    )

    session = SessionLocal()

    try:
        user = get_user_by_username(
            session,
            username,
        )

        if user is None:
            print("LOGIN FAILED")
            return

        if not user.active:
            print("ACCOUNT DISABLED")
            return

        if not verify_password(
            password,
            user.password_hash,
        ):
            print("LOGIN FAILED")
            return

        roles = collect_user_roles(user)
        permissions = collect_user_permissions(user)

        token, expires_at = create_access_token(
            user_id=user.id,
            username=user.username,
            roles=roles,
            permissions=permissions,
        )

        decoded = decode_access_token(token)

        print()
        print("==============================")
        print(" PROJECTX LOCAL LOGIN SUCCESS")
        print("==============================")
        print("User        :", user.username)
        print("Display name:", user.display_name)
        print("Roles       :", roles)
        print("Permissions :", len(permissions))
        print("JWT created :", bool(token))
        print("JWT subject :", decoded["sub"])
        print("Expires at  :", expires_at)

    finally:
        session.close()


if __name__ == "__main__":
    main()