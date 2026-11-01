"""TenantManager and TenantQuerySet — workspace-scoped by construction (§15.4)."""
from __future__ import annotations

from django.db import models

from apps.core.tenancy.context import get_current_workspace_id


class TenantQuerySet(models.QuerySet):
    """Automatically filters by the current workspace context."""

    def for_workspace(self, workspace_id: int) -> "TenantQuerySet":
        return self.filter(workspace_id=workspace_id)


class TenantManager(models.Manager):
    """
    Default manager for TenantModel subclasses.
    Always returns rows scoped to the current workspace context.
    Uses `all_objects` to bypass scoping when needed (archive access, admin).
    """

    def get_queryset(self) -> TenantQuerySet:
        qs = TenantQuerySet(self.model, using=self._db)
        workspace_id = get_current_workspace_id()
        if workspace_id is not None:
            qs = qs.filter(workspace_id=workspace_id)
        return qs


class AllObjectsManager(models.Manager):
    """Bypass tenant scoping — for archive access, admin, reports, background jobs."""

    def get_queryset(self) -> models.QuerySet:
        return models.QuerySet(self.model, using=self._db)
