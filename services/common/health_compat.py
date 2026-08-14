from __future__ import annotations

from common.v1 import common_pb2


def _status_field(response):
    field = response.DESCRIPTOR.fields_by_name.get("status")
    if field is None or field.enum_type is None:
        return None
    return field


def _enum_name(response) -> str:
    field = _status_field(response)
    if field is None:
        return ""
    value = field.enum_type.values_by_number.get(int(getattr(response, "status", 0)))
    return value.name.upper() if value is not None else ""


def _is_negative_name(name: str) -> bool:
    name = name.upper()
    return any(token in name for token in (
        "UNSPECIFIED", "UNKNOWN", "OFFLINE", "NOT_SERVING", "NOTSERVING",
        "UNHEALTHY", "DOWN", "FAILED", "FAILURE", "STOPPED", "UNAVAILABLE",
    ))


def _pick_status_number(field, desired: str) -> int | None:
    desired = (desired or "").strip().upper()
    aliases = {
        "ONLINE": (
            "ONLINE", "HEALTH_STATUS_ONLINE", "STATUS_ONLINE",
            "SERVICE_HEALTH_STATUS_ONLINE", "SERVICE_STATUS_ONLINE",
            "SERVING", "HEALTH_STATUS_SERVING", "STATUS_SERVING",
            "SERVICE_HEALTH_STATUS_SERVING", "SERVICE_STATUS_SERVING",
            "HEALTHY", "HEALTH_STATUS_HEALTHY", "SERVICE_HEALTH_STATUS_HEALTHY",
            "UP", "STATUS_UP", "SERVICE_STATUS_UP", "OK", "STATUS_OK",
        ),
        "DEGRADED": (
            "DEGRADED", "HEALTH_STATUS_DEGRADED", "STATUS_DEGRADED",
            "SERVICE_HEALTH_STATUS_DEGRADED", "SERVICE_STATUS_DEGRADED",
            "PARTIAL", "HEALTH_STATUS_PARTIAL", "SERVICE_HEALTH_STATUS_PARTIAL",
        ),
        "OFFLINE": (
            "OFFLINE", "HEALTH_STATUS_OFFLINE", "STATUS_OFFLINE",
            "SERVICE_HEALTH_STATUS_OFFLINE", "SERVICE_STATUS_OFFLINE",
            "NOT_SERVING", "HEALTH_STATUS_NOT_SERVING", "STATUS_NOT_SERVING",
            "SERVICE_HEALTH_STATUS_NOT_SERVING", "SERVICE_STATUS_NOT_SERVING",
            "DOWN", "UNHEALTHY", "UNAVAILABLE",
        ),
    }

    values = field.enum_type.values_by_name
    for candidate in aliases.get(desired, (desired,)):
        found = values.get(candidate)
        if found is not None:
            return found.number

    # Semantic fallback for differently-prefixed enum values.
    all_values = list(field.enum_type.values)
    if desired == "ONLINE":
        for value in all_values:
            name = value.name.upper()
            if value.number != 0 and not _is_negative_name(name) and any(
                token in name for token in ("ONLINE", "SERVING", "HEALTHY", "UP", "OK")
            ):
                return value.number
        # Final safe fallback: first non-zero value that is not obviously negative.
        for value in all_values:
            if value.number != 0 and not _is_negative_name(value.name):
                return value.number

    if desired == "DEGRADED":
        for value in all_values:
            name = value.name.upper()
            if any(token in name for token in ("DEGRADED", "PARTIAL", "WARNING")):
                return value.number
        # If the contract has only SERVING / NOT_SERVING, degraded maps to NOT_SERVING.
        for value in all_values:
            name = value.name.upper()
            if any(token in name for token in ("NOT_SERVING", "OFFLINE", "UNHEALTHY", "DOWN", "UNAVAILABLE")):
                return value.number

    if desired == "OFFLINE":
        for value in all_values:
            name = value.name.upper()
            if any(token in name for token in ("NOT_SERVING", "OFFLINE", "UNHEALTHY", "DOWN", "UNAVAILABLE")):
                return value.number

    return None


def build_health_response_compat(service: str, desired: str, message: str, version: str = "1.0.0"):
    response = common_pb2.HealthResponse()
    fields = response.DESCRIPTOR.fields_by_name
    for name, value in (
        ("service", service),
        ("service_name", service),
        ("message", message),
        ("version", version),
    ):
        if name in fields:
            setattr(response, name, value)

    field = _status_field(response)
    if field is not None:
        number = _pick_status_number(field, desired)
        if number is not None:
            response.status = number
    return response


def health_status_name(response) -> str:
    name = _enum_name(response)
    return name or str(int(getattr(response, "status", 0)))


def health_category(response) -> str:
    """Return ONLINE, DEGRADED, OFFLINE or UNKNOWN for any compatible common.proto enum."""
    name = _enum_name(response)
    number = int(getattr(response, "status", 0))
    message = str(getattr(response, "message", "") or "").lower()

    if any(token in name for token in ("DEGRADED", "PARTIAL", "WARNING")):
        return "DEGRADED"
    if any(token in name for token in ("NOT_SERVING", "OFFLINE", "UNHEALTHY", "DOWN", "UNAVAILABLE", "FAILED")):
        return "OFFLINE"
    if not _is_negative_name(name) and any(token in name for token in ("ONLINE", "SERVING", "HEALTHY", "UP", "OK")):
        return "ONLINE"

    if number == 0:
        return "UNKNOWN"

    # Last-resort compatibility for non-standard enum names.
    if any(token in message for token in ("unavailable", "offline", "not available", "failed")):
        return "OFFLINE"
    if any(token in message for token in ("degraded", "partial")):
        return "DEGRADED"
    if any(token in message for token in ("available", "online", "healthy", "running")):
        return "ONLINE"
    return "UNKNOWN"
