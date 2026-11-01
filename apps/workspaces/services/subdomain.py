"""Subdomain allocation, validation and release (REQ-WS-13, REQ-WS-15)."""
from __future__ import annotations

from apps.core.errors import Conflict
from apps.core.validators import validate_subdomain, RESERVED_SUBDOMAINS


def allocate_subdomain(slug: str) -> str:
    """
    Validate and reserve a subdomain.
    Raises Conflict with SUBDOMAIN_TAKEN on collision.
    """
    from apps.workspaces.models import Workspace

    slug = slug.lower().strip()
    validate_subdomain(slug)

    if Workspace.objects.filter(subdomain=slug).exists():
        suggestions = _suggestions(slug)
        raise Conflict(
            f"Subdomain '{slug}' is already taken.",
            code="SUBDOMAIN_TAKEN",
            suggestions=suggestions,
        )
    return slug


def check_available(slug: str) -> dict[str, object]:
    from apps.workspaces.models import Workspace

    slug = slug.lower().strip()
    try:
        validate_subdomain(slug)
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}

    taken = Workspace.objects.filter(subdomain=slug).exists()
    return {
        "available": not taken,
        "suggestions": _suggestions(slug) if taken else [],
    }


def release_candidates() -> list[int]:
    """Return workspace IDs eligible for subdomain release (REQ-WS-15)."""
    from apps.workspaces.models import Workspace
    from apps.billing.models import SubscriptionPayment
    from apps.core.enums import WorkspaceStatus, SubPaymentStatus
    from django.utils import timezone
    import datetime

    cutoff = timezone.now() - datetime.timedelta(days=30)
    never_paid_ids = (
        Workspace.objects
        .filter(status=WorkspaceStatus.SETUP, created_at__lt=cutoff, subdomain__isnull=False)
        .exclude(
            id__in=SubscriptionPayment.objects.filter(
                status=SubPaymentStatus.APPROVED
            ).values("workspace_id")
        )
        .values_list("id", flat=True)
    )
    return list(never_paid_ids)


def _suggestions(slug: str) -> list[str]:
    from apps.workspaces.models import Workspace

    candidates = [f"{slug}-1", f"{slug}-2", f"{slug}2", f"my-{slug}"]
    available = []
    for c in candidates:
        try:
            validate_subdomain(c)
            if not Workspace.objects.filter(subdomain=c).exists():
                available.append(c)
        except Exception:  # noqa: BLE001
            pass
    return available[:3]
