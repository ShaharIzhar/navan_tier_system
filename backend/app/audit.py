from __future__ import annotations

from typing import Any

from sqlmodel import Session

from .models import AuditEvent


def record(
    session: Session,
    *,
    entity_type: str,
    action: str,
    prospect_id: str | None = None,
    entity_id: Any = None,
    actor: str = "system",
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        prospect_id=prospect_id,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        action=action,
        actor=actor,
        details=details or {},
    )
    session.add(event)
    return event
