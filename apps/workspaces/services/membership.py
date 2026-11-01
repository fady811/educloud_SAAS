"""Workspace membership management."""
from __future__ import annotations

from apps.core.enums import Role
from apps.core.errors import NotFound, Conflict


def add_student(*, workspace_id: int, user_id: int) -> "WorkspaceMembership":
    from apps.workspaces.models import WorkspaceMembership
    from apps.billing.services.entitlements import check_limit
    from apps.core.enums import LimitKey

    current = WorkspaceMembership.objects.filter(workspace_id=workspace_id, role=Role.STUDENT).count()
    check_limit(workspace_id, LimitKey.MAX_STUDENTS, current)

    membership, created = WorkspaceMembership.objects.get_or_create(
        workspace_id=workspace_id,
        user_id=user_id,
        defaults={"role": Role.STUDENT},
    )
    if not created and membership.role != Role.STUDENT:
        raise Conflict("User already has a different role in this workspace.", code="ROLE_CONFLICT")
    return membership


def remove_member(*, workspace_id: int, user_id: int) -> None:
    from apps.workspaces.models import WorkspaceMembership

    deleted, _ = WorkspaceMembership.objects.filter(
        workspace_id=workspace_id,
        user_id=user_id,
        is_owner=False,
    ).delete()
    if not deleted:
        raise NotFound("Membership not found.")
