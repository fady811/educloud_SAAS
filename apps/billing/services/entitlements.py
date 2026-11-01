"""Entitlement resolution and limit checking (REQ-SUB-17/18)."""
from __future__ import annotations

from apps.core.enums import LimitAction, LimitKey
from apps.core.errors import LimitExceeded


def get_active_subscription(workspace_id: int):
    from apps.billing.models import Subscription
    from apps.core.enums import SubscriptionStatus

    return (
        Subscription.objects.filter(workspace_id=workspace_id, status=SubscriptionStatus.ACTIVE)
        .select_related("package")
        .first()
    )


def get_current_limits(workspace_id: int) -> dict:
    """Return effective limits dict for a workspace."""
    from apps.workspaces.models import Workspace
    from apps.core.enums import LimitKey

    sub = get_active_subscription(workspace_id)
    base = {}
    if sub and sub.entitlement_snapshot:
        snap = sub.entitlement_snapshot
        base = {
            LimitKey.MAX_STUDENTS: snap.get("max_students"),
            LimitKey.STORAGE_GB: snap.get("storage_gb"),
            LimitKey.MAX_SUBJECTS_COURSES: snap.get("max_subjects_courses"),
            LimitKey.MAX_GROUPS: snap.get("max_groups"),
            LimitKey.MAX_TEAM_MEMBERS: snap.get("max_team_members"),
        }
    elif sub:
        pkg = sub.package
        base = {
            LimitKey.MAX_STUDENTS: pkg.max_students,
            LimitKey.STORAGE_GB: float(pkg.storage_gb) if pkg.storage_gb else None,
            LimitKey.MAX_SUBJECTS_COURSES: pkg.max_subjects_courses,
            LimitKey.MAX_GROUPS: pkg.max_groups,
            LimitKey.MAX_TEAM_MEMBERS: pkg.max_team_members,
        }
    # Add addon capacity
    addon_map = _get_addon_extra(workspace_id)
    for key, extra in addon_map.items():
        if key in base and base[key] is not None:
            base[key] = base[key] + extra
    return base


def _get_addon_extra(workspace_id: int) -> dict:
    from apps.billing.models import CapacityAddon
    from apps.core.enums import AddonStatus, AddonType, LimitKey
    from django.utils import timezone

    now = timezone.now()
    from django.db import models as django_models
    active_addons = CapacityAddon.objects.filter(
        workspace_id=workspace_id,
        status=AddonStatus.ACTIVE,
    ).filter(django_models.Q(expires_at__isnull=True) | django_models.Q(expires_at__gt=now))

    result: dict = {}
    type_to_key = {
        AddonType.STUDENT_SLOTS: LimitKey.MAX_STUDENTS,
        AddonType.STORAGE_GB: LimitKey.STORAGE_GB,
    }
    for addon in active_addons:
        key = type_to_key.get(addon.addon_type)
        if key:
            result[key] = result.get(key, 0) + addon.quantity
    return result


def check_limit(workspace_id: int, limit_key: str, current_count: int) -> str:
    """
    Returns LimitAction to take. Raises LimitExceeded when action is BLOCK_NEW.
    """
    from apps.workspaces.models import Workspace

    limits = get_current_limits(workspace_id)
    limit_value = limits.get(limit_key)
    if limit_value is None:
        return LimitAction.WARN  # No limit configured — allow

    try:
        ws = Workspace.objects.only("limit_policy").get(id=workspace_id)
        policy = ws.limit_policy or {}
    except Workspace.DoesNotExist:
        return LimitAction.WARN

    from apps.workspaces.models import DEFAULT_LIMIT_POLICY
    action = policy.get(limit_key, DEFAULT_LIMIT_POLICY.get(limit_key, LimitAction.WARN))

    if current_count >= limit_value:
        if action == LimitAction.BLOCK_NEW:
            raise LimitExceeded(
                limit_key=limit_key,
                limit=limit_value,
                current=current_count,
                remedy="upgrade_plan",
            )
        return action
    return LimitAction.WARN
