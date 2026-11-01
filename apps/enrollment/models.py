"""Enrollment models (§12.4.8)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import EnrollmentStatus, EnrollableType
from apps.core.models import TenantModel


class Enrollment(TenantModel):
    """Student enrollment in a group or course."""
    student_id = models.BigIntegerField()
    enrollable_type = models.CharField(max_length=20, choices=EnrollableType.choices)
    enrollable_id = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    unenrolled_at = models.DateTimeField(null=True, blank=True)
    enrolled_by_id = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "enrollment"
        db_table = "enrollments"
        indexes = [
            models.Index(fields=["workspace", "student_id"], name="enrl_student_idx"),
            models.Index(fields=["workspace", "enrollable_type", "enrollable_id"], name="enrl_target_idx"),
        ]
        unique_together = [("workspace", "student_id", "enrollable_type", "enrollable_id")]
