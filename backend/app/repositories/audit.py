from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.currency import AUDIT_AMOUNT_KEYS, CURRENCY
from backend.app.db.models import AuditEvent

SENSITIVE_AUDIT_KEYS = {
    "password",
    "password_hash",
    "token",
    "jwt_secret",
    "authorization",
    "credentials",
}


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized = str(key).casefold()
            if any(sensitive in normalized for sensitive in SENSITIVE_AUDIT_KEYS):
                return True
            if _contains_sensitive_key(nested_value):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        success: bool,
        actor_id: UUID | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        if details is not None and _contains_sensitive_key(details):
            raise ValueError("Sensitive values are not permitted in audit metadata")
        if details and AUDIT_AMOUNT_KEYS.intersection(details):
            details = {**details, "currency": CURRENCY}
        event = AuditEvent(
            action=action,
            resource_type=resource_type,
            success=success,
            actor_id=actor_id,
            resource_id=resource_id,
            details=details or {},
        )
        self.session.add(event)
        return event
