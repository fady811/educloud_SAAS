"""Content models — Subject, Course, Lesson, LessonContent (§12.4.6)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import (
    GradeLevel, Visibility, PricingType, LessonParentType, LessonContentType,
)
from apps.core.models import TenantModel


class Subject(TenantModel):
    name = models.CharField(max_length=150)
    grade_level = models.CharField(max_length=20, choices=GradeLevel.choices, blank=True)
    color = models.CharField(max_length=7, blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.DRAFT)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "content"
        db_table = "subjects"
        unique_together = [("workspace", "name")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(visibility__in=["DRAFT", "PUBLISHED", "ARCHIVED"]),
                name="subject_visibility_valid",
            ),
        ]


class Course(TenantModel):
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.DRAFT)
    pricing_type = models.CharField(max_length=20, choices=PricingType.choices, default=PricingType.FREE)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cover_image_id = models.BigIntegerField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "content"
        db_table = "courses"
        indexes = [
            models.Index(fields=["workspace", "visibility"], name="course_ws_vis_idx"),
        ]


class Lesson(TenantModel):
    parent_type = models.CharField(max_length=20, choices=LessonParentType.choices)
    parent_id = models.BigIntegerField()
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_free_preview = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "content"
        db_table = "lessons"
        indexes = [
            models.Index(fields=["workspace", "parent_type", "parent_id"], name="lesson_parent_idx"),
        ]


class LessonContent(TenantModel):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="contents")
    content_type = models.CharField(max_length=20, choices=LessonContentType.choices)
    body = models.TextField(blank=True)
    file_id = models.BigIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        app_label = "content"
        db_table = "lesson_contents"


class StudentCourseAccess(TenantModel):
    """Tracks which students can access a course (enrollment-driven or manual)."""
    student_id = models.BigIntegerField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="accesses")
    expires_at = models.DateTimeField(null=True, blank=True)
    granted_by_id = models.BigIntegerField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "content"
        db_table = "student_course_accesses"
        unique_together = [("workspace", "student_id", "course")]
