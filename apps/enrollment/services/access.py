"""Lesson access gate and StudentCourseAccess writer (REQ-ENR-CONTENT-01)."""
from __future__ import annotations

from django.utils import timezone


# ---------------------------------------------------------------------------
# Public writer
# ---------------------------------------------------------------------------

def grant_access(
    *,
    workspace_id: int,
    student_id: int,
    course_id: int,
    paid_until=None,
    granted_by_id: int | None = None,
) -> "StudentCourseAccess":
    """
    Idempotent writer: creates or extends a StudentCourseAccess row.

    paid_until=None means no expiry (one-time purchase, REQ-PAY-04).
    An existing non-revoked row is extended (expires_at updated), never duplicated.
    """
    from apps.content.models import StudentCourseAccess, Course

    course = Course.objects.get(id=course_id, workspace_id=workspace_id)
    access, _ = StudentCourseAccess.objects.update_or_create(
        workspace_id=workspace_id,
        student_id=student_id,
        course=course,
        revoked_at__isnull=True,
        defaults={
            "expires_at": paid_until,
            "granted_by_id": granted_by_id,
        },
    )
    return access


def revoke_access(*, workspace_id: int, student_id: int, course_id: int) -> None:
    """Mark the non-revoked access row as revoked (teacher manual revocation)."""
    from apps.content.models import StudentCourseAccess, Course
    StudentCourseAccess.objects.filter(
        workspace_id=workspace_id,
        student_id=student_id,
        course__id=course_id,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())


# ---------------------------------------------------------------------------
# Access check — raises typed domain error, never returns False
# ---------------------------------------------------------------------------

def check_lesson_access(
    *,
    workspace_id: int,
    student_id: int,
    lesson_id: int,
    user: object = None,
) -> None:
    """
    Enforce lesson access for a student.  Raises a domain error on denial;
    returns None on success.

    Evaluation order (spec §1.2):
      1. workspace serves students        → WORKSPACE_NOT_ACTIVE / GRACE_PERIOD_RESTRICTED
      2. lesson exists, not archived      → NOT_FOUND
      3. parent course exists & PUBLISHED → NOT_FOUND
      4. free preview OR free course      → ALLOW
      5. active enrollment covers it      → ENROLLMENT_INACTIVE
      6. access row grants it, unexpired  → PAYMENT_REQUIRED / PAYMENT_PERIOD_EXPIRED
      7. enrollment date window           → OUTSIDE_DATE_WINDOW
    """
    from apps.content.models import Lesson, Course, StudentCourseAccess
    from apps.enrollment.models import Enrollment
    from apps.core.enums import Visibility, EnrollmentStatus, WorkspaceStatus, ErrorCode
    from apps.core.errors import NotFound, PermissionDeniedError
    from apps.workspaces.models import Workspace
    from apps.workspaces.services.lifecycle import grace_capability

    # Step 1: workspace state
    try:
        ws = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        raise NotFound("Workspace not found.")

    if ws.status == WorkspaceStatus.GRACE_PERIOD:
        # Delegate to grace_capability — "view_lesson" is in _GRACE_ALLOWED_ACTIONS
        effective_user = user
        if effective_user is None:
            from apps.accounts.models import User
            try:
                effective_user = User.objects.get(id=student_id)
            except User.DoesNotExist:
                pass
        if effective_user is not None and not grace_capability(workspace_id, "view_lesson", effective_user):
            raise PermissionDeniedError(
                "Content is not available during grace period.",
                code=ErrorCode.GRACE_PERIOD_RESTRICTED,
            )
    elif ws.status not in (WorkspaceStatus.ACTIVE,):
        raise PermissionDeniedError(
            "This workspace is not currently serving students.",
            code=ErrorCode.WORKSPACE_NOT_ACTIVE,
        )

    # Step 2: lesson exists
    try:
        lesson = Lesson.objects.get(id=lesson_id, workspace_id=workspace_id, archived_at__isnull=True)
    except Lesson.DoesNotExist:
        raise NotFound("Lesson not found.")

    # Step 3: parent course must be PUBLISHED
    if lesson.parent_type != "COURSE":
        raise NotFound("Lesson not found.")
    try:
        course = Course.objects.get(
            id=lesson.parent_id,
            workspace_id=workspace_id,
            visibility=Visibility.PUBLISHED,
            archived_at__isnull=True,
        )
    except Course.DoesNotExist:
        raise NotFound("Lesson not found.")

    # Step 4: free preview — always allow; no access row needed
    if lesson.is_free_preview:
        return

    # Step 5: active enrollment (COURSE or SUBJECT) — required even for free courses
    enrollment = _find_active_enrollment(workspace_id, student_id, course)
    if enrollment is None:
        raise PermissionDeniedError(
            "You are not enrolled in this course.",
            code=ErrorCode.ENROLLMENT_INACTIVE,
        )

    # Step 4b: free course — enrolled students need no access row
    from apps.core.enums import PricingType
    if course.pricing_type == PricingType.FREE:
        return

    # Step 6: StudentCourseAccess row
    try:
        access = StudentCourseAccess.objects.get(
            workspace_id=workspace_id,
            student_id=student_id,
            course=course,
            revoked_at__isnull=True,
        )
        if access.expires_at and access.expires_at < timezone.now():
            raise PermissionDeniedError(
                "Your access to this course has expired.",
                code=ErrorCode.PAYMENT_PERIOD_EXPIRED,
                details={"expires_at": access.expires_at.isoformat(), "course_id": course.id},
            )
    except StudentCourseAccess.DoesNotExist:
        raise PermissionDeniedError(
            "Payment is required to access this course.",
            code=ErrorCode.PAYMENT_REQUIRED,
            details={"course_id": course.id, "price": str(course.price) if course.price else None},
        )

    # Step 7: enrollment date window
    if enrollment.expires_at and enrollment.expires_at < timezone.now():
        raise PermissionDeniedError(
            "Your enrollment has passed its end date.",
            code=ErrorCode.OUTSIDE_DATE_WINDOW,
        )


def _find_active_enrollment(workspace_id: int, student_id: int, course):
    """Return the first active enrollment for the student covering this course."""
    from apps.enrollment.models import Enrollment
    from apps.core.enums import EnrollmentStatus

    # Direct COURSE enrollment
    enrollment = Enrollment.objects.filter(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type="COURSE",
        enrollable_id=course.id,
        status=EnrollmentStatus.ACTIVE,
    ).first()
    if enrollment:
        return enrollment

    # SUBJECT enrollment covering this course's subject
    if course.subject_id:
        enrollment = Enrollment.objects.filter(
            workspace_id=workspace_id,
            student_id=student_id,
            enrollable_type="SUBJECT",
            enrollable_id=course.subject_id,
            status=EnrollmentStatus.ACTIVE,
        ).first()
    return enrollment


# ---------------------------------------------------------------------------
# Legacy bool shim — kept for backward compat with any callers
# (LessonContentView uses check_lesson_access directly now)
# ---------------------------------------------------------------------------

def lesson_accessible(*, workspace_id: int, student_id: int, lesson_id: int) -> bool:
    """Deprecated shim — prefer check_lesson_access() which carries error codes."""
    try:
        check_lesson_access(
            workspace_id=workspace_id,
            student_id=student_id,
            lesson_id=lesson_id,
        )
        return True
    except Exception:
        return False
