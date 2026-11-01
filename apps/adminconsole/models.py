"""Admin console models: ContentReport."""
from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel


class ContentReport(TimeStampedModel):
    """Reports filed against workspace content (REQ-ADM-*)."""

    workspace_id = models.BigIntegerField(db_index=True)
    reporter_id = models.BigIntegerField()
    content_type = models.CharField(max_length=50)
    content_id = models.BigIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, default="OPEN", db_index=True)
    reviewed_by_id = models.BigIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True)

    class Meta:
        app_label = "adminconsole"
        db_table = "adminconsole_content_reports"
        indexes = [
            models.Index(fields=["workspace_id", "status"], name="cr_ws_status_idx"),
        ]
