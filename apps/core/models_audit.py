"""AuditLog model — append-only, no FKs (DR-038, §12.7.1, REQ-ADMIN-11)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import ActorType


class AuditLog(models.Model):
    """
    Immutable audit record.
    No FKs so the append-only trigger can be absolute and workspace purge can complete (DR-038).
    actor_id and target_id are plain integers/strings — denormalized intentionally.
    """

    workspace_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    actor_id = models.BigIntegerField(null=True, blank=True)
    actor_type = models.CharField(max_length=20, choices=ActorType.choices, default=ActorType.USER)
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=100, db_index=True)
    target_id = models.CharField(max_length=255, blank=True, default="")
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    reason = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "core"
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace_id", "-created_at"], name="audit_ws_time_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_time_idx"),
            models.Index(fields=["target_type", "target_id"], name="audit_target_idx"),
        ]

    def save(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        if self.pk is not None:
            raise ValueError("AuditLog rows are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:  # type: ignore[override]
        raise ValueError("AuditLog rows may not be deleted.")

    def __str__(self) -> str:
        return f"[{self.created_at}] {self.actor_type}:{self.actor_id} → {self.action} on {self.target_type}:{self.target_id}"
