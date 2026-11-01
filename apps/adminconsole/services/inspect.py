"""Admin inspection and moderation services."""
from __future__ import annotations

from apps.core.tenancy.context import admin_context


def get_workspace_overview(workspace_id: int) -> dict:
    from apps.workspaces.models import Workspace, WorkspaceMembership
    from apps.billing.models import Subscription
    from apps.core.enums import SubscriptionStatus

    with admin_context():
        try:
            ws = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            from apps.core.errors import NotFound
            raise NotFound("Workspace not found.")

        member_count = WorkspaceMembership.objects.filter(workspace_id=workspace_id).count()
        active_sub = Subscription.objects.filter(
            workspace_id=workspace_id,
            status=SubscriptionStatus.ACTIVE,
        ).select_related("package").first()

    return {
        "workspace_id": workspace_id,
        "subdomain": ws.subdomain,
        "status": ws.status,
        "member_count": member_count,
        "active_subscription": {
            "package": active_sub.package.slug if active_sub else None,
            "ends_at": active_sub.ends_at.isoformat() if active_sub else None,
        },
    }


def quarantine_workspace(workspace_id: int, *, actor_id: int, reason: str) -> None:
    from apps.workspaces.models import Workspace
    from apps.workspaces.services.lifecycle import transition
    from apps.core.enums import WorkspaceStatus

    with admin_context():
        ws = Workspace.objects.get(id=workspace_id)
        transition(ws, WorkspaceStatus.FROZEN, actor_id=actor_id, reason=reason)
