"""Assessment models: Exam, Question, QuestionBankEntry, ExamAttempt, Assignment, AssignmentSubmission."""
from __future__ import annotations

from django.db import models

from apps.core.enums import AttemptStatus, ExamStatus, QuestionType
from apps.core.models import TenantModel
from apps.core.validators import sanitize_html


class Exam(TenantModel):
    lesson = models.ForeignKey("content.Lesson", on_delete=models.CASCADE, related_name="exams", null=True, blank=True)
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    duration_minutes = models.SmallIntegerField()
    pass_score = models.SmallIntegerField(default=50)
    max_attempts = models.SmallIntegerField(default=1)
    shuffle_questions = models.BooleanField(default=False)
    shuffle_choices = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=ExamStatus.choices, default=ExamStatus.DRAFT, db_index=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "assessments"
        db_table = "assessments_exams"


class Question(TenantModel):
    exam = models.ForeignKey("assessments.Exam", on_delete=models.CASCADE, related_name="questions", null=True, blank=True)
    bank_entry = models.ForeignKey("assessments.QuestionBankEntry", on_delete=models.SET_NULL, null=True, blank=True)
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    body = models.TextField()
    choices = models.JSONField(default=list)
    correct_answer = models.JSONField(null=True, blank=True)
    points = models.SmallIntegerField(default=1)
    display_order = models.SmallIntegerField(default=0)

    class Meta:
        app_label = "assessments"
        db_table = "assessments_questions"
        ordering = ["display_order"]

    def save(self, *args, **kwargs):
        if self.body:
            self.body = sanitize_html(self.body)
        super().save(*args, **kwargs)


class QuestionBankEntry(TenantModel):
    subject = models.ForeignKey("content.Subject", on_delete=models.CASCADE, related_name="bank_entries")
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    body = models.TextField()
    choices = models.JSONField(default=list)
    correct_answer = models.JSONField(null=True, blank=True)
    points = models.SmallIntegerField(default=1)
    tags = models.JSONField(default=list)

    class Meta:
        app_label = "assessments"
        db_table = "assessments_question_bank"


class ExamAttempt(TenantModel):
    """Server-authoritative timing (REQ-ASS-08)."""

    exam = models.ForeignKey("assessments.Exam", on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="exam_attempts")
    status = models.CharField(max_length=20, choices=AttemptStatus.choices, default=AttemptStatus.IN_PROGRESS, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(db_index=True)
    answers = models.JSONField(default=dict)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        app_label = "assessments"
        db_table = "assessments_attempts"
        indexes = [
            models.Index(fields=["workspace", "student", "status"], name="att_student_status_idx"),
            models.Index(fields=["deadline_at", "status"], name="att_deadline_idx"),
        ]


class Assignment(TenantModel):
    lesson = models.ForeignKey("content.Lesson", on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments")
    group = models.ForeignKey("groups.Group", on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments")
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    max_score = models.SmallIntegerField(default=100)
    allow_late = models.BooleanField(default=True)

    class Meta:
        app_label = "assessments"
        db_table = "assessments_assignments"


class AssignmentSubmission(TenantModel):
    assignment = models.ForeignKey("assessments.Assignment", on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="assignment_submissions")
    file_id = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "assessments"
        db_table = "assessments_submissions"
        unique_together = [("assignment", "student")]
