from __future__ import annotations

import math
from datetime import timedelta, timezone

import grpc
import jwt
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import func, select

from auth.v1 import auth_pb2, auth_pb2_grpc
from database.session import SessionLocal
from services.auth.config import QR_CREDENTIAL_VALID_DAYS
from services.auth.models import AuditLog, Notification, QrCredential, StaffProfile, User, utc_now
from services.auth.repository import (
    collect_user_permissions,
    collect_user_roles,
    get_notification_by_id,
    get_qr_by_token_hash,
    get_role_by_code,
    get_staff_by_email,
    get_staff_by_employee_number,
    get_user_by_id,
    get_user_by_login_identifier,
    get_user_by_username,
    list_active_users_with_role,
    list_pending_users,
    list_staff_directory,
    list_users,
    user_has_permission,
)
from services.common.internal_auth import require_internal_service
from services.auth.security import (
    create_access_token,
    decode_access_token,
    generate_qr_payload,
    hash_password,
    qr_payload_hash,
    verify_password,
)


DASHBOARD_BY_ROLE = {
    "ADMIN_HOPITAL": "/administration",
    "RESPONSABLE_RH": "/ressources-humaines",
    "AGENT_ACCUEIL": "/accueil",
    "RESP_HOSPITALISATION": "/hospitalisation",
    "INFIRMIER": "/hospitalisation",
    "CAISSIER": "/paiement",
    "MEDECIN": "/consultation",
    "LABORANTIN": "/laboratoire",
    "PHARMACIEN": "/pharmacie",
    "RESPONSABLE_LOGISTIQUE": "/pharmacie",
    "SAGE_FEMME": "/maternite",
    "RESPONSABLE_BI": "/statistiques",
}
DASHBOARD_PRIORITY = list(DASHBOARD_BY_ROLE.keys())


def datetime_to_timestamp(value):
    timestamp = Timestamp()
    timestamp.FromDatetime(value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value)
    return timestamp


def dashboard_for_user(user: User) -> str:
    roles = set(collect_user_roles(user))
    for role in DASHBOARD_PRIORITY:
        if role in roles:
            return DASHBOARD_BY_ROLE[role]
    return "/"


def _qr_is_live(item: QrCredential) -> bool:
    now = utc_now()
    return bool(item.active and (item.expires_at is None or item.expires_at > now))


def _qr_enabled(user: User) -> bool:
    return any(_qr_is_live(item) for item in getattr(user, "qr_credentials", []))


def _status_value(user: User):
    status = (user.approval_status or "ACTIVE").upper()
    if status in {"PENDING", "PENDING_APPROVAL"}:
        return auth_pb2.USER_STATUS_PENDING_APPROVAL
    if status == "REJECTED":
        return auth_pb2.USER_STATUS_REJECTED
    if status == "DISABLED" or not user.active:
        return auth_pb2.USER_STATUS_DISABLED
    return auth_pb2.USER_STATUS_ACTIVE


def staff_to_proto(profile: StaffProfile | None):
    if profile is None:
        return None
    result = auth_pb2.StaffProfile(
        employee_number=profile.employee_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email or "",
        phone=profile.phone or "",
        department=profile.department,
        job_title=profile.job_title,
        registered_by_id=profile.registered_by_id or "",
    )
    if profile.registered_at is not None:
        result.registered_at.CopyFrom(datetime_to_timestamp(profile.registered_at))
    return result


def user_to_proto(user: User):
    result = auth_pb2.User(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=_status_value(user),
        roles=collect_user_roles(user),
        permissions=collect_user_permissions(user),
        qr_enabled=_qr_enabled(user),
    )
    profile = staff_to_proto(getattr(user, "staff_profile", None))
    if profile is not None:
        result.staff_profile.CopyFrom(profile)
    return result


def notification_to_proto(notification: Notification):
    response = auth_pb2.Notification(
        id=notification.id,
        recipient_id=notification.recipient_id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        status=(auth_pb2.NOTIFICATION_STATUS_READ if notification.status == "READ" else auth_pb2.NOTIFICATION_STATUS_UNREAD),
        created_at=datetime_to_timestamp(notification.created_at),
    )
    if notification.read_at is not None:
        response.read_at.CopyFrom(datetime_to_timestamp(notification.read_at))
    return response


def _metadata_token(context) -> str:
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization":
            value = item.value.strip()
            if value.lower().startswith("bearer "):
                return value[7:].strip()
    return ""


def _audit(session, context, *, actor_id=None, action, resource_id=None, outcome="SUCCESS", reason=None, correlation_id=None):
    session.add(
        AuditLog(
            actor_id=actor_id,
            service="auth",
            action=action,
            resource_id=resource_id,
            correlation_id=correlation_id,
            outcome=outcome,
            reason=reason,
            peer=context.peer() if context is not None else None,
        )
    )


def _token_version_matches(user: User, payload: dict) -> bool:
    try:
        token_version = int(payload.get("auth_version", 1))
    except (TypeError, ValueError):
        return False
    return token_version == int(getattr(user, "auth_version", 1) or 1)


def _require_actor(session, context, permission: str | None = None) -> User:
    token = _metadata_token(context)
    if not token:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Bearer token is required.")
    try:
        payload = decode_access_token(token)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or expired access token.")
    user_id = payload.get("sub")
    user = get_user_by_id(session, user_id) if isinstance(user_id, str) else None
    if user is None or not user.active or user.approval_status != "ACTIVE":
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Account is not active.")
    if not _token_version_matches(user, payload):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Session is no longer valid. Please sign in again.")
    if permission and not user_has_permission(user, permission):
        _audit(session, context, actor_id=user.id, action="permission_denied", resource_id=user.id, outcome="DENIED", reason=permission)
        session.commit()
        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Insufficient permission.")
    return user


def _validate_login_identity(username: str, password: str, display_name: str, context):
    if not username or not password or not display_name:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Username, password and display name are required.")
    if len(username) < 3 or len(username) > 100:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Username must contain 3 to 100 characters.")
    if len(password) < 8:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Password must contain at least 8 characters.")
    if len(display_name) > 150:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Display name is too long.")


def _clean_email(email: str) -> str | None:
    value = email.strip().lower()
    return value or None


def _validate_staff_request(request, context):
    required = {
        "employee_number": request.employee_number.strip(),
        "first_name": request.first_name.strip(),
        "last_name": request.last_name.strip(),
        "department": request.department.strip(),
        "job_title": request.job_title.strip(),
        "username": request.username.strip(),
        "temporary_password": request.temporary_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Missing required staff fields: " + ", ".join(missing))
    _validate_login_identity(required["username"], required["temporary_password"], f"{required['first_name']} {required['last_name']}", context)
    email = _clean_email(request.email)
    if email is not None and ("@" not in email or len(email) > 180):
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid email address.")
    return required, email


def _issue_qr(session, user: User, actor_id: str | None) -> tuple[QrCredential, str]:
    now = utc_now()
    for credential in user.qr_credentials:
        if credential.active:
            credential.active = False
            credential.revoked_at = now
    payload, token_hash = generate_qr_payload()
    credential = QrCredential(
        user_id=user.id,
        token_hash=token_hash,
        active=True,
        issued_at=now,
        expires_at=now + timedelta(days=max(1, QR_CREDENTIAL_VALID_DAYS)),
        issued_by_id=actor_id,
    )
    session.add(credential)
    session.flush()
    if credential not in user.qr_credentials:
        user.qr_credentials.append(credential)
    return credential, payload


def _revoke_qr(user: User) -> bool:
    changed = False
    now = utc_now()
    for credential in user.qr_credentials:
        if credential.active:
            credential.active = False
            credential.revoked_at = now
            changed = True
    return changed


def _login_response(user: User):
    roles = collect_user_roles(user)
    permissions = collect_user_permissions(user)
    access_token, expires_at = create_access_token(
        user_id=user.id, username=user.username, roles=roles, permissions=permissions,
        auth_version=getattr(user, "auth_version", 1),
    )
    return auth_pb2.LoginResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_at=datetime_to_timestamp(expires_at),
        user=user_to_proto(user),
        dashboard_route=dashboard_for_user(user),
    )


def _notify(session, recipient_id: str, notification_type: str, title: str, body: str):
    session.add(Notification(recipient_id=recipient_id, type=notification_type, title=title, body=body, status="UNREAD"))


def _page_values(page_request):
    if page_request is None:
        return 1, 50
    page = page_request.page if page_request.page > 0 else 1
    page_size = page_request.page_size if page_request.page_size > 0 else 50
    return page, min(page_size, 100)


def staff_directory_entry_to_proto(user: User):
    profile = user.staff_profile
    return auth_pb2.StaffDirectoryEntry(
        user_id=user.id,
        display_name=user.display_name,
        employee_number=profile.employee_number if profile else "",
        department=profile.department if profile else "",
        job_title=profile.job_title if profile else "",
        active=bool(user.active and user.approval_status == "ACTIVE"),
        roles=collect_user_roles(user),
    )


def _validate_notification_payload(request, context):
    recipient_id = request.recipient_id.strip()
    title = request.title.strip()
    body = request.body.strip()
    if not recipient_id or not title or not body:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "recipient_id, title and body are required.")
    return recipient_id, title, body


class AuthService(auth_pb2_grpc.AuthServiceServicer):
    def Login(self, request, context):
        identifier = request.identifier.strip() or request.username.strip()
        password = request.password
        if not identifier or not password:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Username/email and password are required.")
        session = SessionLocal()
        try:
            user = get_user_by_login_identifier(session, identifier)
            if user is None or not verify_password(password, user.password_hash):
                _audit(session, context, action="login_password", outcome="DENIED", reason="Invalid credentials")
                session.commit()
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid username/email or password.")
            if user.approval_status in {"PENDING", "PENDING_APPROVAL"}:
                _audit(session, context, actor_id=user.id, action="login_password", resource_id=user.id, outcome="DENIED", reason="Pending administrator approval")
                session.commit()
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Account is waiting for administrator approval.")
            if user.approval_status == "REJECTED":
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Account access request was rejected.")
            if not user.active or user.approval_status == "DISABLED":
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "This account is disabled.")
            if not collect_user_roles(user):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "No active role is assigned to this account.")
            response = _login_response(user)
            _audit(session, context, actor_id=user.id, action="login_password", resource_id=user.id)
            session.commit()
            return response
        finally:
            session.close()

    def LoginWithQr(self, request, context):
        payload = request.qr_payload.strip()
        if not payload:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "QR payload is required.")
        try:
            token_hash = qr_payload_hash(payload)
        except ValueError:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or revoked QR credential.")
        session = SessionLocal()
        try:
            credential = get_qr_by_token_hash(session, token_hash)
            if credential is None or not credential.active:
                _audit(session, context, action="login_qr", outcome="DENIED", reason="Invalid or revoked QR")
                session.commit()
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or revoked QR credential.")
            if credential.expires_at is not None and credential.expires_at <= utc_now():
                credential.active = False
                credential.revoked_at = utc_now()
                _audit(session, context, action="login_qr", outcome="DENIED", reason="Expired QR")
                session.commit()
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "QR credential has expired.")
            user = credential.user
            if user is None or not user.active or user.approval_status != "ACTIVE":
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Account is not active.")
            if not collect_user_roles(user):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "No active role is assigned to this account.")
            credential.last_used_at = utc_now()
            response = _login_response(user)
            _audit(session, context, actor_id=user.id, action="login_qr", resource_id=user.id)
            session.commit()
            return response
        finally:
            session.close()

    def ValidateToken(self, request, context):
        access_token = request.access_token.strip()
        if not access_token:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Access token is required.")
        try:
            payload = decode_access_token(access_token)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return auth_pb2.ValidateTokenResponse(valid=False)
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id.strip():
            return auth_pb2.ValidateTokenResponse(valid=False)
        session = SessionLocal()
        try:
            user = get_user_by_id(session, user_id)
            if user is None or not user.active or user.approval_status != "ACTIVE":
                return auth_pb2.ValidateTokenResponse(valid=False)
            if not _token_version_matches(user, payload):
                return auth_pb2.ValidateTokenResponse(valid=False)
            return auth_pb2.ValidateTokenResponse(valid=True, user=user_to_proto(user), dashboard_route=dashboard_for_user(user))
        finally:
            session.close()

    def GetCurrentUser(self, request, context):
        token = request.access_token.strip() or _metadata_token(context)
        if not token:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Access token is required.")
        try:
            payload = decode_access_token(token)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or expired access token.")
        session = SessionLocal()
        try:
            user = get_user_by_id(session, str(payload.get("sub", "")))
            if user is None or not user.active or user.approval_status != "ACTIVE":
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Account is not active.")
            if not _token_version_matches(user, payload):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Session is no longer valid. Please sign in again.")
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def ChangeMyPassword(self, request, context):
        current_password = request.current_password
        new_password = request.new_password
        if not current_password or not new_password:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "current_password and new_password are required.")
        if len(new_password) < 8:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "New password must contain at least 8 characters.")
        if current_password == new_password:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "New password must be different from the current password.")
        session = SessionLocal()
        try:
            actor = _require_actor(session, context)
            if not verify_password(current_password, actor.password_hash):
                _audit(session, context, actor_id=actor.id, action="change_my_password", resource_id=actor.id, outcome="DENIED", reason="Current password mismatch")
                session.commit()
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Current password is incorrect.")
            actor.password_hash = hash_password(new_password)
            actor.auth_version = int(getattr(actor, "auth_version", 1) or 1) + 1
            _audit(session, context, actor_id=actor.id, action="change_my_password", resource_id=actor.id)
            session.commit()
            return auth_pb2.ChangeMyPasswordResponse(
                changed=True,
                reauthentication_required=True,
                message="Password changed. Existing JWT sessions are invalid; sign in again. QR credential remains independently managed.",
            )
        finally:
            session.close()

    def UpdateMyProfile(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context)
            if actor.staff_profile is None:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "This account has no staff profile.")
            if not request.HasField("email") and not request.HasField("phone"):
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Provide email and/or phone to update.")
            profile = actor.staff_profile
            changed = []
            if request.HasField("email"):
                email = _clean_email(request.email)
                if email is not None and ("@" not in email or len(email) > 180):
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid email address.")
                if email is not None:
                    other = get_staff_by_email(session, email)
                    if other is not None and other.user_id != actor.id:
                        context.abort(grpc.StatusCode.ALREADY_EXISTS, "Email address already exists.")
                profile.email = email
                changed.append("email")
            if request.HasField("phone"):
                phone = request.phone.strip() or None
                if phone is not None and len(phone) > 40:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Phone number is too long.")
                profile.phone = phone
                changed.append("phone")
            _audit(session, context, actor_id=actor.id, action="update_my_profile", resource_id=actor.id, reason=",".join(changed))
            session.commit()
            user = get_user_by_id(session, actor.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def RegisterStaff(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.staff.create")
            required, email = _validate_staff_request(request, context)
            existing_staff = get_staff_by_employee_number(session, required["employee_number"])
            if existing_staff is not None:
                # Idempotent service-to-service retry: HR may retry provisioning after a network timeout.
                existing_user = get_user_by_id(session, existing_staff.user_id)
                if existing_user is not None and existing_user.username == required["username"]:
                    return auth_pb2.UserResponse(user=user_to_proto(existing_user))
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Employee number already exists.")
            if get_user_by_username(session, required["username"]) is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Username is already in use.")
            if email and get_staff_by_email(session, email) is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Email address already exists.")

            display_name = f"{required['first_name']} {required['last_name']}".strip()
            user = User(
                username=required["username"],
                password_hash=hash_password(required["temporary_password"]),
                display_name=display_name,
                active=False,
                approval_status="PENDING_APPROVAL",
            )
            session.add(user)
            session.flush()
            user.staff_profile = StaffProfile(
                user_id=user.id,
                employee_number=required["employee_number"],
                first_name=required["first_name"],
                last_name=required["last_name"],
                email=email,
                phone=request.phone.strip() or None,
                department=required["department"],
                job_title=required["job_title"],
                registered_by_id=actor.id,
            )
            _audit(session, context, actor_id=actor.id, action="register_staff", resource_id=user.id, reason=required["employee_number"])
            for admin in list_active_users_with_role(session, "ADMIN_HOPITAL"):
                _notify(
                    session,
                    admin.id,
                    "STAFF_ACCOUNT_PENDING",
                    "Nouveau compte personnel à valider",
                    f"{display_name} ({required['employee_number']}) - {required['job_title']} / {required['department']}",
                )
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def CreateUser(self, request, context):
        username = request.username.strip()
        password = request.password
        display_name = request.display_name.strip()
        _validate_login_identity(username, password, display_name, context)
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.users.create")
            if get_user_by_username(session, username) is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Username is already in use.")
            role_codes = sorted(set(code.strip() for code in request.roles if code.strip()))
            if not role_codes:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "At least one role is required.")
            roles = []
            for code in role_codes:
                role = get_role_by_code(session, code)
                if role is None or not role.active:
                    context.abort(grpc.StatusCode.NOT_FOUND, f"Unknown or inactive role: {code}")
                roles.append(role)
            user = User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                active=True,
                approval_status="ACTIVE",
                approved_at=utc_now(),
                approved_by_id=actor.id,
            )
            user.roles = roles
            session.add(user)
            session.flush()
            _audit(session, context, actor_id=actor.id, action="create_user_direct", resource_id=user.id, reason=",".join(role_codes))
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def ListPendingUsers(self, request, context):
        session = SessionLocal()
        try:
            _require_actor(session, context, "auth.staff.read")
            page, page_size = _page_values(request.page if request.HasField("page") else None)
            users, total = list_pending_users(session, page, page_size)
            total_pages = math.ceil(total / page_size) if total else 0
            return auth_pb2.ListUsersResponse(
                users=[user_to_proto(item) for item in users],
                page={"page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages},
            )
        finally:
            session.close()

    def ListUsers(self, request, context):
        session = SessionLocal()
        try:
            _require_actor(session, context, "auth.users.read")
            page, page_size = _page_values(request.page if request.HasField("page") else None)
            users, total = list_users(session, page, page_size, request.status)
            total_pages = math.ceil(total / page_size) if total else 0
            return auth_pb2.ListUsersResponse(
                users=[user_to_proto(item) for item in users],
                page={"page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages},
            )
        finally:
            session.close()

    def ApproveUser(self, request, context):
        user_id = request.user_id.strip()
        role_codes = sorted(set(code.strip() for code in request.role_codes if code.strip()))
        if not user_id or not role_codes:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "User id and at least one role are required.")
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.users.approve")
            if not user_has_permission(actor, "auth.roles.assign"):
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Role assignment permission is required.")
            user = get_user_by_id(session, user_id)
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            if user.id == actor.id:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "An administrator cannot approve their own account through this workflow.")
            if user.approval_status not in {"PENDING", "PENDING_APPROVAL"}:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only a pending staff account can be approved.")
            roles = []
            for code in role_codes:
                role = get_role_by_code(session, code)
                if role is None or not role.active:
                    context.abort(grpc.StatusCode.NOT_FOUND, f"Unknown or inactive role: {code}")
                roles.append(role)
            user.roles = roles
            user.active = True
            user.approval_status = "ACTIVE"
            user.approved_at = utc_now()
            user.approved_by_id = actor.id
            credential, qr_payload = _issue_qr(session, user, actor.id)
            _notify(session, user.id, "ACCOUNT_APPROVED", "Accès ProjectX approuvé", "Votre compte a été approuvé. Vous pouvez vous connecter avec vos identifiants ou votre QR personnel.")
            _audit(session, context, actor_id=actor.id, action="approve_staff_access", resource_id=user.id, reason=",".join(role_codes))
            _audit(session, context, actor_id=actor.id, action="issue_qr", resource_id=user.id)
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.ApproveUserResponse(
                user=user_to_proto(user),
                qr_payload=qr_payload,
                qr_expires_at=datetime_to_timestamp(credential.expires_at),
            )
        finally:
            session.close()

    def RejectUser(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.users.approve")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            if user.approval_status not in {"PENDING", "PENDING_APPROVAL"}:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only a pending account can be rejected.")
            user.active = False
            user.approval_status = "REJECTED"
            _revoke_qr(user)
            _audit(session, context, actor_id=actor.id, action="reject_staff_access", resource_id=user.id, reason=request.reason.strip() or None)
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def DisableUser(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.users.disable")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            if user.id == actor.id:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "An administrator cannot disable their current account.")
            user.active = False
            user.approval_status = "DISABLED"
            _revoke_qr(user)
            _audit(session, context, actor_id=actor.id, action="disable_user", resource_id=user.id, reason=request.reason.strip() or None)
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def AssignRole(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.roles.assign")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            if not user.active or user.approval_status != "ACTIVE":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Approve the account before changing active roles.")
            role = get_role_by_code(session, request.role_code.strip())
            if role is None or not role.active:
                context.abort(grpc.StatusCode.NOT_FOUND, "Role not found or inactive.")
            if role not in user.roles:
                user.roles.append(role)
            _audit(session, context, actor_id=actor.id, action="assign_role", resource_id=user.id, reason=role.code)
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def UpdateStaffProfile(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.staff.update")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None or user.staff_profile is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Staff user not found.")
            profile = user.staff_profile
            if request.first_name.strip(): profile.first_name = request.first_name.strip()
            if request.last_name.strip(): profile.last_name = request.last_name.strip()
            if request.email.strip():
                email = request.email.strip().lower()
                if "@" not in email: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid email address.")
                other = get_staff_by_email(session, email)
                if other is not None and other.user_id != user.id:
                    context.abort(grpc.StatusCode.ALREADY_EXISTS, "Email address already exists.")
                profile.email = email
            if request.phone.strip(): profile.phone = request.phone.strip()
            if request.department.strip(): profile.department = request.department.strip()
            if request.job_title.strip(): profile.job_title = request.job_title.strip()
            user.display_name = f"{profile.first_name} {profile.last_name}".strip()
            _audit(session, context, actor_id=actor.id, action="update_staff_profile", resource_id=user.id)
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def SyncStaffEmploymentStatus(self, request, context):
        status = request.employment_status.strip().upper()
        if status not in {"ACTIVE", "SUSPENDED", "INACTIVE", "TERMINATED"}:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Unknown employment_status.")
        if not request.reason.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "reason is required.")
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.staff.update")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            if status == "ACTIVE":
                if user.approval_status == "ACTIVE" and collect_user_roles(user):
                    user.active = True
                # Pending/rejected/disabled-by-admin identities are not promoted by HR.
            else:
                user.active = False
                if status == "TERMINATED":
                    _revoke_qr(user)
            _audit(session, context, actor_id=actor.id, action="sync_employment_access", resource_id=user.id, reason=f"{status}: {request.reason.strip()}")
            session.commit()
            user = get_user_by_id(session, user.id)
            return auth_pb2.UserResponse(user=user_to_proto(user))
        finally:
            session.close()

    def ListStaffDirectory(self, request, context):
        session = SessionLocal()
        try:
            _require_actor(session, context, "auth.directory.read")
            page, page_size = _page_values(request.page if request.HasField("page") else None)
            users, total = list_staff_directory(
                session, role_code=request.role_code, search=request.search, active_only=request.active_only,
                page=page, page_size=page_size,
            )
            total_pages = math.ceil(total / page_size) if total else 0
            return auth_pb2.ListStaffDirectoryResponse(
                entries=[staff_directory_entry_to_proto(user) for user in users],
                page={"page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages},
            )
        finally:
            session.close()

    def GetStaffDirectoryEntry(self, request, context):
        session = SessionLocal()
        try:
            _require_actor(session, context, "auth.directory.read")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None or user.staff_profile is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Staff user not found.")
            return auth_pb2.StaffDirectoryEntryResponse(entry=staff_directory_entry_to_proto(user))
        finally:
            session.close()

    def IssueQrCredential(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.qr.manage")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            if not user.active or user.approval_status != "ACTIVE" or not collect_user_roles(user):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "QR can only be issued to an approved active account with a role.")
            credential, payload = _issue_qr(session, user, actor.id)
            _audit(session, context, actor_id=actor.id, action="rotate_qr", resource_id=user.id)
            session.commit()
            return auth_pb2.QrCredentialResponse(
                user_id=user.id,
                qr_payload=payload,
                issued_at=datetime_to_timestamp(credential.issued_at),
                expires_at=datetime_to_timestamp(credential.expires_at),
                active=True,
            )
        finally:
            session.close()

    def RevokeQrCredential(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "auth.qr.manage")
            user = get_user_by_id(session, request.user_id.strip())
            if user is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found.")
            _revoke_qr(user)
            _audit(session, context, actor_id=actor.id, action="revoke_qr", resource_id=user.id)
            session.commit()
            return auth_pb2.QrCredentialStatusResponse(user_id=user.id, active=False)
        finally:
            session.close()

    def SendNotification(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "notification.send")
            recipient_id, title, body = _validate_notification_payload(request, context)
            recipient = get_user_by_id(session, recipient_id)
            if recipient is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Recipient not found.")
            notification = Notification(
                recipient_id=recipient.id,
                type=request.type.strip() or "GENERAL",
                title=title,
                body=body,
                status="UNREAD",
            )
            session.add(notification)
            session.flush()
            _audit(session, context, actor_id=actor.id, action="send_notification", resource_id=notification.id)
            session.commit()
            return auth_pb2.NotificationResponse(notification=notification_to_proto(notification))
        finally:
            session.close()

    def SendSystemNotification(self, request, context):
        require_internal_service(context)
        session = SessionLocal()
        try:
            recipient_id, title, body = _validate_notification_payload(request, context)
            recipient = get_user_by_id(session, recipient_id)
            if recipient is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Recipient not found.")
            notification = Notification(
                recipient_id=recipient.id, type=request.type.strip() or "SYSTEM",
                title=title, body=body, status="UNREAD",
            )
            session.add(notification); session.flush()
            _audit(session, context, action="send_system_notification", resource_id=notification.id,
                   correlation_id=request.correlation_id.strip() or None, reason=request.source_service.strip() or "internal-service")
            session.commit()
            return auth_pb2.NotificationResponse(notification=notification_to_proto(notification))
        finally:
            session.close()

    def ListSystemRecipientsByRole(self, request, context):
        require_internal_service(context)
        role_code = request.role_code.strip().upper()
        if not role_code:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "role_code is required.")
        session = SessionLocal()
        try:
            users = list_active_users_with_role(session, role_code)
            return auth_pb2.SystemRecipientsResponse(recipients=[
                auth_pb2.SystemRecipient(
                    user_id=user.id, display_name=user.display_name,
                    employee_number=(user.staff_profile.employee_number if user.staff_profile else ""),
                ) for user in users
            ])
        finally:
            session.close()

    def ListNotifications(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "notification.read")
            recipient_id = request.recipient_id.strip() or actor.id
            if recipient_id != actor.id and not user_has_permission(actor, "auth.users.read"):
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Cannot read another user's notifications.")
            page, page_size = _page_values(request.page if request.HasField("page") else None)
            total = session.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_id == recipient_id)) or 0
            items = list(
                session.scalars(
                    select(Notification)
                    .where(Notification.recipient_id == recipient_id)
                    .order_by(Notification.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                ).all()
            )
            total_pages = math.ceil(total / page_size) if total else 0
            return auth_pb2.ListNotificationsResponse(
                notifications=[notification_to_proto(item) for item in items],
                page={"page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages},
            )
        finally:
            session.close()

    def MarkNotificationRead(self, request, context):
        session = SessionLocal()
        try:
            actor = _require_actor(session, context, "notification.read")
            notification = get_notification_by_id(session, request.notification_id.strip())
            if notification is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Notification not found.")
            if notification.recipient_id != actor.id and not user_has_permission(actor, "auth.users.read"):
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Cannot update another user's notification.")
            notification.status = "READ"
            notification.read_at = utc_now()
            session.commit()
            return auth_pb2.NotificationResponse(notification=notification_to_proto(notification))
        finally:
            session.close()
