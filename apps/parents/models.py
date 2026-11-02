"""Parent-student linkage model (§12.4.10)."""
from __future__ import annotations

import secrets

from django.db import models
from apps.core.models import TenantModel


def _generate_code() -> str:
    return secrets.token_urlsafe(12)  # 16 URL-safe chars


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


class ParentLinkCode(TenantModel):
    """
    Short-lived code a student generates; a parent redeems it to create a link.
    Codes are single-use and expire after TTL_MINUTES.
    """
    TTL_MINUTES = 30

    student_id = models.BigIntegerField()
    code = models.CharField(max_length=32, unique=True, default=_generate_code)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        app_label = "parents"
        db_table = "parent_link_codes"
        indexes = [
            models.Index(fields=["code"], name="plc_code_idx"),
            models.Index(fields=["workspace", "student_id"], name="plc_student_idx"),
        ]
