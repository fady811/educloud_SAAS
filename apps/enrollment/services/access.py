"""Lesson access gate — 7-step evaluation order (REQ-ENR-CONTENT-01)."""
from __future__ import annotations

from django.utils import timezone


def lesson_accessible(*, workspace_id: int, student_id: int, lesson_id: int) -> bool:
    """
    Return True if the student may access lesson content.

    Evaluation order:
      1. Lesson must exist and not be archived.
      2. Lesson's parent course must exist and be PUBLISHED.
      3. Free preview — always accessible if is_free_preview is True.
      4. Active enrollment in the course is required for non-preview lessons.
      5. Enrollment must not be expired or cancelled.
      6. StudentCourseAccess row must exist and not be revoked; honour expires_at if set.
      7. Workspace must be ACTIVE (frozen/grace-period workspaces block content).
    """
    from apps.content.models import Lesson, Course, StudentCourseAccess
    from apps.enrollment.models import Enrollment
    from apps.core.enums import Visibility, EnrollmentStatus, WorkspaceStatus
    from apps.workspaces.models import Workspace

    # Step 1: lesson exists
    try:
        lesson = Lesson.objects.get(id=lesson_id, workspace_id=workspace_id, archived_at__isnull=True)
    except Lesson.DoesNotExist:
        return False

    # Step 2: parent course must be PUBLISHED
    if lesson.parent_type != "COURSE":
        return False
    try:
        course = Course.objects.get(
            id=lesson.parent_id,
            workspace_id=workspace_id,
            visibility=Visibility.PUBLISHED,
            archived_at__isnull=True,
        )
    except Course.DoesNotExist:
        return False

    # Step 3: free preview
    if lesson.is_free_preview:
        return True

    # Step 4 & 5: active enrollment in the course
    enrolled = Enrollment.objects.filter(
        workspace_id=workspace_id,
        student_id=student_id,
        enrollable_type="COURSE",
        enrollable_id=course.id,
        status=EnrollmentStatus.ACTIVE,
    ).exists()
    if not enrolled:
        return False

    # Step 6: StudentCourseAccess row
    try:
        access = StudentCourseAccess.objects.get(
            workspace_id=workspace_id,
            student_id=student_id,
            course=course,
            revoked_at__isnull=True,
        )
        if access.expires_at and access.expires_at < timezone.now():
            return False
    except StudentCourseAccess.DoesNotExist:
        return False

    # Step 7: workspace active
    try:
        ws = Workspace.objects.get(id=workspace_id)
        if ws.status not in (WorkspaceStatus.ACTIVE, WorkspaceStatus.GRACE_PERIOD):
            return False
    except Workspace.DoesNotExist:
        return False

    return True
