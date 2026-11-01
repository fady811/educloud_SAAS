"""Team member invitation and permission management."""
from __future__ import annotations

from django.db import transaction

from apps.accounts.enums import PermissionKey
from apps.core.errors import Conflict, NotFound


def invite_team_member(*, workspace_id: int, email: str, permission_keys: list[str], invited_by_id: int) -> "TeamInvitation":
    from apps.accounts.models import TeamInvitation
    import secrets

    with transaction.atomic():
        existing = TeamInvitation.objects.filter(workspace_id=workspace_id, email=email, accepted_at__isnull=True).first()
        if existing:
            raise Conflict("Invitation already pending.", code="INVITATION_PENDING")
        return TeamInvitation.objects.create(
            workspace_id=workspace_id,
            email=email,
            token=secrets.token_urlsafe(32),
            permission_keys=permission_keys,
            invited_by_id=invited_by_id,
        )


def set_permissions(*, workspace_id: int, user_id: int, permission_keys: list[str]) -> None:
    from apps.accounts.models import TeamMemberPermission

    with transaction.atomic():
        TeamMemberPermission.objects.filter(user_id=user_id, workspace_id=workspace_id).delete()
        TeamMemberPermission.objects.bulk_create([
            TeamMemberPermission(user_id=user_id, workspace_id=workspace_id, permission_key=k)
            for k in permission_keys
        ])
