"""
Audit log writer — the ONLY writer of AuditLog rows (§5.14, REQ-ADMIN-09).
core.audit.record() is the single entry point.
"""
from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.core.enums import ActorType
from apps.core.logging import get_request_id


def record(
    *,
    actor_id: int | None,
    actor_type: str = ActorType.USER,
    action: str,
    target_type: str,
    target_id: int | str | None = None,
    workspace_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str = "",
    request_id: str | None = None,
) -> None:
    """
    Write an immutable audit log row.
    Must be called INSIDE the transaction that performs the action
    (side-effect delivery uses on_commit; audit rows are part of the transaction).
    """
    from apps.core.models_audit import AuditLog  # lazy import — avoids cycle

    AuditLog.objects.create(
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else "",
        before=before or {},
        after=after or {},
        reason=reason,
        request_id=request_id or get_request_id(),
        created_at=timezone.now(),
    )
