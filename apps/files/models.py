"""StoredFile model (§12.4.5, REQ-FILE-*)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import FileCategory, ScanStatus
from apps.core.models import TenantModel


class StoredFile(TenantModel):
    """Tracks every file uploaded by a workspace (REQ-FILE-01)."""

    key = models.CharField(max_length=512, unique=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()
    category = models.CharField(max_length=30, choices=FileCategory.choices)
    scan_status = models.CharField(max_length=20, choices=ScanStatus.choices, default=ScanStatus.PENDING, db_index=True)
    scan_result = models.JSONField(null=True, blank=True)
    uploaded_by_id = models.BigIntegerField(null=True, blank=True)
    is_public = models.BooleanField(default=False)
    # Soft-delete (orphan cleanup)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "files"
        db_table = "stored_files"
        indexes = [
            models.Index(fields=["workspace", "category"], name="sf_ws_cat_idx"),
            models.Index(fields=["scan_status"], name="sf_scan_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.original_name} ({self.scan_status})"
