"""Group models (§12.4.7 — class groups, schedules, attendance)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import GroupStatus, AttendanceStatus
from apps.core.models import TenantModel


class Group(TenantModel):
    """A class group (دفعة / مجموعة) owned by a workspace."""
    name = models.CharField(max_length=150)
    subject_id = models.BigIntegerField(null=True, blank=True)
    teacher_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=GroupStatus.choices, default=GroupStatus.ACTIVE)
    max_students = models.PositiveIntegerField(null=True, blank=True)
    color = models.CharField(max_length=7, blank=True)
    description = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "groups"
        db_table = "groups_classgroup"
        indexes = [
            models.Index(fields=["workspace", "status"], name="grp_ws_status_idx"),
        ]


class GroupMembership(TenantModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    student_id = models.BigIntegerField()
    joined_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "groups"
        db_table = "groups_memberships"
        unique_together = [("workspace", "group", "student_id")]


class Session(TenantModel):
    """A scheduled class session."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=255, blank=True)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    notes = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "groups"
        db_table = "groups_attendance_sessions"
        indexes = [
            models.Index(fields=["workspace", "group", "scheduled_at"], name="sess_grp_at_idx"),
        ]


class AttendanceRecord(TenantModel):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="attendances")
    student_id = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    notes = models.CharField(max_length=500, blank=True)
    recorded_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        app_label = "groups"
        db_table = "attendance_records"
        unique_together = [("workspace", "session", "student_id")]
