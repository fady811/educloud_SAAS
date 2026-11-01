"""Workspace invite link service."""
from __future__ import annotations

import secrets
from django.utils import timezone

from apps.core.errors import NotFound


def create_invite_link(*, workspace_id: int, created_by_id: int, subject_id=None, group_id=None):
    from apps.accounts.models import WorkspaceInviteLink

    token = secrets.token_urlsafe(24)
    link = WorkspaceInviteLink.objects.create(
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        token=token,
        subject_id=subject_id,
        group_id=group_id,
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )
    return link


def resolve_invite_link(token: str) -> dict:
    from apps.accounts.models import WorkspaceInviteLink

    link = WorkspaceInviteLink.objects.filter(
        token=token,
        expires_at__gt=timezone.now(),
    ).select_related("workspace").first()
    if not link:
        raise NotFound("Invite link not found or expired")

    return {
        "workspace_id": link.workspace_id,
        "workspace_subdomain": link.workspace.subdomain,
        "subject_id": link.subject_id,
        "group_id": link.group_id,
    }
