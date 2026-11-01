"""Workspace provisioning service."""
from __future__ import annotations

from django.db import transaction

from apps.core import audit
from apps.core.enums import WorkspaceStatus
from apps.workspaces.services.subdomain import allocate_subdomain


def create_workspace(*, owner_id: int, subdomain: str, display_name: str = ""):
    from apps.workspaces.models import Workspace, WorkspaceMembership
    from apps.core.enums import ActorType

    with transaction.atomic():
        allocate_subdomain(subdomain)
        ws = Workspace.objects.create(
            subdomain=subdomain,
            status=WorkspaceStatus.SETUP,
            settings_json={"display_name": display_name or subdomain},
        )
        WorkspaceMembership.objects.create(
            user_id=owner_id,
            workspace=ws,
            role="OWNER",
            is_owner=True,
        )
        audit.record(
            actor_id=owner_id,
            actor_type=ActorType.USER,
            action="WORKSPACE_CREATED",
            target_type="Workspace",
            target_id=ws.id,
            workspace_id=ws.id,
            after={"subdomain": subdomain, "display_name": display_name},
        )
    return ws
