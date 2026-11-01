"""Base model abstractions (§8.1, §10.5)."""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Adds created_at and updated_at to every model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(TimeStampedModel):
    """
    Base for all workspace-scoped tables (§12.3 group B).
    workspace_id is NOT NULL and every composite index leads with it.
    """

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        db_index=False,  # composite index is created per model
    )

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """Adds deleted_at for soft-deleted rows (§3.1)."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    def soft_delete(self) -> None:
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self) -> None:
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    class Meta:
        abstract = True


class ArchivableModel(TimeStampedModel):
    """Adds archived_at for soft-archived content (§3.1)."""

    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    suspension_reason = models.TextField(blank=True, default="")
    suspended_at = models.DateTimeField(null=True, blank=True)

    def archive(self) -> None:
        self.archived_at = timezone.now()
        self.save(update_fields=["archived_at", "updated_at"])

    def restore_from_archive(self) -> None:
        self.archived_at = None
        self.save(update_fields=["archived_at", "updated_at"])

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    class Meta:
        abstract = True


# Import concrete models so Django's app registry discovers them when the
# 'core' app loads. Both files declare app_label="core" explicitly; these
# imports are the only change needed — no model code is moved or altered.
#
# Circular-import note: idempotency.py imports TimeStampedModel from this
# module. Python adds a module to sys.modules before executing it, so by
# the time this bottom-of-file import triggers idempotency.py's own import,
# TimeStampedModel is already defined above — no ImportError occurs.
from apps.core.models_audit import AuditLog as AuditLog  # noqa: F401
from apps.core.idempotency import IdempotencyKey as IdempotencyKey  # noqa: F401
