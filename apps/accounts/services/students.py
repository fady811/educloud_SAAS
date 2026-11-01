"""Student management within a workspace."""
from __future__ import annotations

from apps.core.enums import Role
from apps.core.errors import NotFound


def get_students(workspace_id: int):
    from apps.workspaces.models import WorkspaceMembership
    return (
        WorkspaceMembership.objects.filter(workspace_id=workspace_id, role=Role.STUDENT)
        .select_related("user")
        .order_by("user__full_name")
    )


def deactivate_student(*, workspace_id: int, student_id: int, actor_id: int) -> None:
    from apps.workspaces.models import WorkspaceMembership
    from django.utils import timezone

    try:
        membership = WorkspaceMembership.objects.get(workspace_id=workspace_id, user_id=student_id, role=Role.STUDENT)
    except WorkspaceMembership.DoesNotExist:
        raise NotFound("Student not found in workspace.")
    membership.is_active = False
    membership.save(update_fields=["is_active"])
