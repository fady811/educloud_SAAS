"""Workspace Celery tasks (§20.3)."""
from __future__ import annotations

from celery import shared_task


@shared_task(queue="default")
def expire_grace_period_workspaces() -> None:
    """Transition GRACE_PERIOD workspaces to DEACTIVATED when grace expires."""
    from apps.workspaces.models import Workspace
    from apps.workspaces.services.lifecycle import transition
    from apps.core.enums import WorkspaceStatus, DeactivationCause, ActorType
    from django.utils import timezone

    now = timezone.now()
    # Find workspaces in GRACE_PERIOD where the subscription expired > grace_period_days ago
    # For each, check if their grace window has passed
    candidates = Workspace.objects.filter(status=WorkspaceStatus.GRACE_PERIOD)
    for ws in candidates:
        # Check last subscription expiry
        from apps.billing.models import Subscription
        last_sub = (
            Subscription.objects
            .filter(workspace=ws, status="EXPIRED")
            .order_by("-expires_at")
            .first()
        )
        if last_sub:
            import datetime
            grace_end = last_sub.expires_at + datetime.timedelta(days=ws.grace_period_days)
            if now >= grace_end:
                transition(
                    ws,
                    WorkspaceStatus.DEACTIVATED,
                    actor_type=ActorType.SYSTEM,
                    reason="Grace period expired",
                    deactivation_cause=DeactivationCause.NON_PAYMENT,
                )


@shared_task(queue="default")
def release_stale_subdomains() -> None:
    """Release subdomains of never-paid 30+ day old workspaces (REQ-WS-15)."""
    from apps.workspaces.services.subdomain import release_candidates
    from apps.workspaces.models import Workspace
    from apps.core import audit
    from apps.core.enums import ActorType

    ids = release_candidates()
    for ws_id in ids:
        Workspace.objects.filter(id=ws_id).update(subdomain=None)
        audit.record(
            actor_id=None,
            actor_type=ActorType.SYSTEM,
            action="SUBDOMAIN_RELEASED",
            target_type="Workspace",
            target_id=ws_id,
        )


@shared_task(queue="default")
def purge_expired_workspaces() -> None:
    """Hard-delete workspaces past their purge_after date (REQ-WS-10)."""
    from apps.workspaces.models import Workspace
    from apps.core.enums import WorkspaceStatus
    from django.utils import timezone

    now = timezone.now()
    expired = Workspace.objects.filter(
        status=WorkspaceStatus.DELETED,
        purge_after__lte=now,
        deleted_at__isnull=False,
    )
    for ws in expired:
        # Hard delete in dependency order — actual implementation would cascade carefully
        # TODO: delete all tenant data in order, then R2 objects, then the workspace row
        pass
