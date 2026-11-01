"""Parent-student linkage model (§12.4.10)."""
from __future__ import annotations

from django.db import models
from apps.core.models import TenantModel


class ParentStudentLink(TenantModel):
    parent_id = models.BigIntegerField()
    student_id = models.BigIntegerField()
    relationship = models.CharField(max_length=50, blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    unlinked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "parents"
        db_table = "parent_student_links"
        unique_together = [("workspace", "parent_id", "student_id")]
        indexes = [
            models.Index(fields=["workspace", "parent_id"], name="psl_parent_idx"),
            models.Index(fields=["workspace", "student_id"], name="psl_student_idx"),
        ]
