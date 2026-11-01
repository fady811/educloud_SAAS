"""
Workspace lifecycle state machine (§6.1, REQ-WS-07).
transition() is THE ONLY writer of Workspace.status.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.enums import ActorType, DeactivationCause, WorkspaceStatus
from apps.core.errors import Conflict


# ---------------------------------------------------------------------------
# Allowed transitions
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    WorkspaceStatus.SETUP: [WorkspaceStatus.PENDING_PAYMENT],
    WorkspaceStatus.PENDING_PAYMENT: [WorkspaceStatus.PENDING_APPROVAL, WorkspaceStatus.SETUP],
    WorkspaceStatus.PENDING_APPROVAL: [WorkspaceStatus.ACTIVE, WorkspaceStatus.PENDING_PAYMENT],
    WorkspaceStatus.ACTIVE: [WorkspaceStatus.GRACE_PERIOD, WorkspaceStatus.FROZEN, WorkspaceStatus.DEACTIVATED, WorkspaceStatus.DELETED],
    WorkspaceStatus.GRACE_PERIOD: [WorkspaceStatus.ACTIVE, WorkspaceStatus.DEACTIVATED, WorkspaceStatus.FROZEN, WorkspaceStatus.DELETED],
    WorkspaceStatus.FROZEN: [WorkspaceStatus.ACTIVE, WorkspaceStatus.DEACTIVATED, WorkspaceStatus.DELETED],
    WorkspaceStatus.DEACTIVATED: [WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETED],
    WorkspaceStatus.DELETED: [],
}


def transition(
    workspace: "Workspace",  # type: ignore[name-defined]
    to_status: str,
    *,
    actor_id: int | None = None,
    actor_type: str = ActorType.SYSTEM,
    reason: str = "",
    deactivation_cause: str | None = None,
) -> "Workspace":  # type: ignore[name-defined]
    """
    The only writer of Workspace.status.
    Validates the transition, writes history, emits audit + notification on_commit.
    """
    from apps.core import audit
    from apps.workspaces.models import WorkspaceStatusHistory

    if to_status not in ALLOWED_TRANSITIONS.get(workspace.status, []):
        raise Conflict(
            f"Transition from {workspace.status} to {to_status} is not allowed.",
            code="ILLEGAL_TRANSITION",
        )

    with transaction.atomic():
        from apps.workspaces.models import Workspace as _WS
        workspace = _WS.objects.select_for_update().get(pk=workspace.pk)
        from_status = workspace.status

        workspace.status = to_status
        if to_status == WorkspaceStatus.DEACTIVATED:
            workspace.deactivation_cause = deactivation_cause
        elif to_status == WorkspaceStatus.ACTIVE:
            workspace.deactivation_cause = None
        if to_status == WorkspaceStatus.DELETED:
            workspace.deleted_at = timezone.now()
            workspace.purge_after = timezone.now() + __import__("datetime").timedelta(days=workspace.retention_days)

        workspace.save(update_fields=["status", "deactivation_cause", "deleted_at", "purge_after", "updated_at"])

        WorkspaceStatusHistory.objects.create(
            workspace=workspace,
            from_status=from_status,
            to_status=to_status,
            triggered_by_id=actor_id,
            trigger_type=actor_type,
            reason=reason,
        )

        audit.record(
            actor_id=actor_id,
            actor_type=actor_type,
            action=f"WORKSPACE_{to_status}",
            target_type="Workspace",
            target_id=workspace.id,
            workspace_id=workspace.id,
            before={"status": from_status},
            after={"status": to_status},
            reason=reason,
        )

        transaction.on_commit(lambda: _notify_transition(workspace.id, from_status, to_status))

    return workspace


def student_access_allowed(workspace: "Workspace") -> bool:  # type: ignore[name-defined]
    """Single predicate used by middleware (REQ-WS-03)."""
    return workspace.status in (WorkspaceStatus.ACTIVE, WorkspaceStatus.GRACE_PERIOD)


# Grace period capability gate (REQ-WS-08a)
_GRACE_DENIED_ACTIONS = frozenset({
    "enroll",
    "submit_assignment",
    "start_exam",
    "send_message",
    "submit_payment_proof",
})

_GRACE_ALLOWED_ACTIONS = frozenset({
    "view_lesson",
    "view_grades",
    "view_attendance",
    "view_announcements",
    "continue_exam",
})


def grace_capability(workspace_id: int, action: str, user: object) -> bool:
    """
    Returns True if the action is allowed in GRACE_PERIOD for this user.
    Called by GracePeriodGate permission class.
    """
    from apps.workspaces.models import Workspace, WorkspaceMembership
    from apps.core.enums import Role

    try:
        ws = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        return False

    if ws.status != WorkspaceStatus.GRACE_PERIOD:
        return True  # not in grace — not restricted

    # Teachers and team members are unaffected (REQ-WS-08a)
    try:
        membership = WorkspaceMembership.objects.get(user=user, workspace_id=workspace_id)
        if membership.role in (Role.TEACHER, Role.TEAM_MEMBER):
            return True
    except WorkspaceMembership.DoesNotExist:
        pass

    if action in _GRACE_DENIED_ACTIONS:
        return False
    return True


def _notify_transition(workspace_id: int, from_status: str, to_status: str) -> None:
    try:
        from apps.notifications.services.dispatch import notify
        from apps.core.enums import NotificationCategory
        from apps.workspaces.models import WorkspaceMembership
        from apps.core.enums import Role

        owner = WorkspaceMembership.objects.filter(
            workspace_id=workspace_id, is_owner=True
        ).select_related("user").first()
        if owner:
            notify(
                user_id=owner.user_id,
                workspace_id=workspace_id,
                category=NotificationCategory.SUBSCRIPTION_STATUS_CHANGED,
                payload={"from_status": from_status, "to_status": to_status},
            )
    except Exception:  # noqa: BLE001
        pass
