"""Enrollment eligibility checks (REQ-ENR-02)."""
from __future__ import annotations

from apps.core.errors import Conflict, LimitExceeded


def check_enrollment_eligibility(*, workspace_id: int, student_id: int, enrollable_type: str, enrollable_id: int) -> None:
    from apps.enrollment.models import Enrollment
    from apps.core.enums import EnrollmentStatus

    existing = Enrollment.objects.filter(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type=enrollable_type,
        enrollable_id=enrollable_id,
        status=EnrollmentStatus.ACTIVE,
    ).exists()
    if existing:
        raise Conflict("Student is already enrolled.", code="ALREADY_ENROLLED")


def enroll(*, workspace_id: int, student_id: int, enrollable_type: str, enrollable_id: int):
    from apps.enrollment.models import Enrollment
    from apps.billing.services.entitlements import check_limit
    from apps.core.enums import LimitKey

    check_enrollment_eligibility(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type=enrollable_type,
        enrollable_id=enrollable_id,
    )
    current = Enrollment.objects.filter(workspace_id=workspace_id, status="ACTIVE").count()
    check_limit(workspace_id, LimitKey.MAX_STUDENTS, current)

    return Enrollment.objects.create(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type=enrollable_type,
        enrollable_id=enrollable_id,
    )
