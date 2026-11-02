"""Student management within a workspace."""
from __future__ import annotations

from apps.core.enums import Role
from apps.core.errors import NotFound


def get_students(workspace_id: int):
    from apps.workspaces.models import WorkspaceMembership
    return (
        WorkspaceMembership.objects.filter(workspace_id=workspace_id, role=Role.STUDENT)
        .select_related("user")
        .order_by("user__last_name", "user__first_name")
    )


def create_student(
    *,
    workspace_id: int,
    email: str | None = None,
    phone: str | None = None,
    first_name: str = "",
    last_name: str = "",
    actor_id: int,
) -> "WorkspaceMembership":  # type: ignore[name-defined]
    from apps.workspaces.models import WorkspaceMembership, Workspace
    from apps.billing.services.entitlements import check_limit
    from apps.core.enums import LimitKey
    from apps.accounts.services.registration import register_user
    from apps.core.errors import Conflict
    from apps.accounts.models import User

    # Check seat limit against active STUDENT memberships
    current = WorkspaceMembership.objects.filter(
        workspace_id=workspace_id, role=Role.STUDENT
    ).count()
    check_limit(workspace_id, LimitKey.MAX_STUDENTS, current)

    # Reuse existing user or create new one
    user = None
    if email:
        user = User.objects.filter(email__iexact=email).first()
    elif phone:
        from apps.core.validators import normalize_phone
        phone = normalize_phone(phone)
        user = User.objects.filter(phone=phone).first()

    if user is None:
        import secrets
        user, _ = register_user(
            email=email,
            phone=phone,
            password=secrets.token_urlsafe(16),
            first_name=first_name,
            last_name=last_name,
        )

    if WorkspaceMembership.objects.filter(user=user, workspace_id=workspace_id).exists():
        raise Conflict("User is already a member of this workspace.", code="ALREADY_MEMBER")

    membership = WorkspaceMembership.objects.create(
        user=user,
        workspace_id=workspace_id,
        role=Role.STUDENT,
        is_owner=False,
    )
    return membership


def deactivate_student(*, workspace_id: int, student_id: int, actor_id: int) -> None:
    from apps.workspaces.models import WorkspaceMembership
    from django.utils import timezone

    try:
        membership = WorkspaceMembership.objects.get(workspace_id=workspace_id, user_id=student_id, role=Role.STUDENT)
    except WorkspaceMembership.DoesNotExist:
        raise NotFound("Student not found in workspace.")
    membership.is_active = False
    membership.save(update_fields=["is_active"])
