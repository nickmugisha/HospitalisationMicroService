from __future__ import annotations

import logging

import grpc

from auth.v1 import auth_pb2, auth_pb2_grpc
from services.common.internal_auth import internal_metadata

logger = logging.getLogger("projectx.common.notifications")


def send_system_notification(*, auth_target: str, recipient_id: str, notification_type: str, title: str, body: str,
                             source_service: str, correlation_id: str = "", timeout: float = 3.0) -> bool:
    if not recipient_id.strip():
        return False
    try:
        with grpc.insecure_channel(auth_target) as channel:
            auth_pb2_grpc.AuthServiceStub(channel).SendSystemNotification(
                auth_pb2.SystemNotificationRequest(
                    recipient_id=recipient_id.strip(), type=notification_type.strip() or "SYSTEM",
                    title=title.strip(), body=body.strip(), source_service=source_service.strip(),
                    correlation_id=correlation_id.strip(),
                ), metadata=internal_metadata(), timeout=timeout,
            )
        return True
    except Exception:
        logger.warning("system notification failed source=%s recipient=%s", source_service, recipient_id, exc_info=True)
        return False


def list_role_recipients(*, auth_target: str, role_code: str, timeout: float = 3.0) -> list[str]:
    try:
        with grpc.insecure_channel(auth_target) as channel:
            response = auth_pb2_grpc.AuthServiceStub(channel).ListSystemRecipientsByRole(
                auth_pb2.SystemRecipientsByRoleRequest(role_code=role_code.strip().upper()),
                metadata=internal_metadata(), timeout=timeout,
            )
        return [item.user_id for item in response.recipients if item.user_id]
    except Exception:
        logger.warning("system recipient lookup failed role=%s", role_code, exc_info=True)
        return []
