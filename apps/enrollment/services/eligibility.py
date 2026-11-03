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


def enroll(
    *,
    workspace_id: int,
    student_id: int,
    enrollable_type: str,
    enrollable_id: int,
    enrolled_by_id: int | None = None,
):
    from apps.enrollment.models import Enrollment
    from apps.billing.services.entitlements import check_limit
    from apps.core.enums import LimitKey, PricingType, EnrollableType

    check_enrollment_eligibility(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type=enrollable_type,
        enrollable_id=enrollable_id,
    )
    current = Enrollment.objects.filter(workspace_id=workspace_id, status="ACTIVE").count()
    check_limit(workspace_id, LimitKey.MAX_STUDENTS, current)

    enrollment = Enrollment.objects.create(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type=enrollable_type,
        enrollable_id=enrollable_id,
        enrolled_by_id=enrolled_by_id,
    )

    # Auto-grant access for FREE courses so students can immediately access content
    # without a payment approval step.
    if enrollable_type == EnrollableType.COURSE:
        try:
            from apps.content.models import Course
            course = Course.objects.get(id=enrollable_id, workspace_id=workspace_id)
            if course.pricing_type == PricingType.FREE:
                from apps.enrollment.services.access import grant_access
                grant_access(
                    workspace_id=workspace_id,
                    student_id=student_id,
                    course_id=course.id,
                    paid_until=None,
                    granted_by_id=enrolled_by_id,
                )
        except Exception:
            pass  # Access row is a best-effort optimisation; the FREE branch in
                  # check_lesson_access does not require it.

    return enrollment
