"""Workspace branding service."""
from __future__ import annotations

from apps.core import audit


def update_branding(workspace_id: int, data: dict, *, actor_id: int):
    from apps.workspaces.models import Workspace
    from django.db import transaction

    allowed = {"display_name", "logo_url", "primary_color", "secondary_color"}
    filtered = {k: v for k, v in data.items() if k in allowed}

    with transaction.atomic():
        ws = Workspace.objects.select_for_update().get(id=workspace_id)
        old = {k: ws.settings_json.get(k) for k in filtered}
        ws.settings_json.update(filtered)
        ws.save(update_fields=["settings_json", "updated_at"])
        audit.record(
            actor_id=actor_id,
            action="WORKSPACE_BRANDING_UPDATED",
            target_type="Workspace",
            target_id=workspace_id,
            workspace_id=workspace_id,
            before=old,
            after=filtered,
        )
    return ws
