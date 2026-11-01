"""Exam attempt lifecycle: start, submit, auto-submit expired (REQ-ASS-08)."""
from __future__ import annotations

import datetime

from django.db import transaction
from django.utils import timezone

from apps.core.enums import AttemptStatus
from apps.core.errors import Conflict, ValidationFailed


def start_attempt(*, exam_id: int, student_id: int, workspace_id: int) -> "ExamAttempt":
    from apps.assessments.models import Exam, ExamAttempt

    with transaction.atomic():
        exam = Exam.objects.select_for_update().get(id=exam_id)
        existing = ExamAttempt.objects.filter(
            exam=exam, student_id=student_id, workspace_id=workspace_id,
            status=AttemptStatus.IN_PROGRESS,
        ).first()
        if existing:
            return existing

        count = ExamAttempt.objects.filter(
            exam=exam, student_id=student_id, workspace_id=workspace_id,
        ).count()
        if count >= exam.max_attempts:
            raise Conflict("Max attempts reached.", code="MAX_ATTEMPTS_REACHED")

        deadline_at = timezone.now() + datetime.timedelta(minutes=exam.duration_minutes)
        return ExamAttempt.objects.create(
            workspace_id=workspace_id,
            exam=exam,
            student_id=student_id,
            deadline_at=deadline_at,
            status=AttemptStatus.IN_PROGRESS,
        )


def submit_attempt(*, attempt_id: int, student_id: int, answers: dict) -> "ExamAttempt":
    from apps.assessments.models import ExamAttempt

    with transaction.atomic():
        attempt = ExamAttempt.objects.select_for_update().get(id=attempt_id, student_id=student_id)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise Conflict("Attempt already submitted.", code="ATTEMPT_ALREADY_SUBMITTED")
        if timezone.now() > attempt.deadline_at:
            raise ValidationFailed("Submission past deadline; will be auto-submitted.")
        attempt.answers = answers
        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=["answers", "status", "submitted_at", "updated_at"])
    return attempt


def auto_submit_expired():
    from apps.assessments.models import ExamAttempt

    expired = ExamAttempt.objects.filter(
        status=AttemptStatus.IN_PROGRESS,
        deadline_at__lt=timezone.now(),
    )
    count = expired.update(
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now(),
    )
    return count
