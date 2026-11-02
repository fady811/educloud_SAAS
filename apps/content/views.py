"""Content views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission, ALL_MEMBERS
from apps.accounts.enums import PermissionKey
from apps.content.serializers import (
    CourseSerializer, CourseWriteSerializer, LessonSerializer, SubjectSerializer,
)

_STUDENT_PARENT = frozenset(["STUDENT", "PARENT"])


class SubjectListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.CONTENT_CREATE},
    }

    def _is_student_or_parent(self, request: Request) -> bool:
        from apps.workspaces.models import WorkspaceMembership
        try:
            m = WorkspaceMembership.objects.get(
                user=request.user, workspace_id=request.workspace_id
            )
            return m.role in _STUDENT_PARENT
        except Exception:  # noqa: BLE001
            return False

    def get(self, request: Request) -> Response:
        from apps.content.models import Subject
        from apps.core.enums import Visibility
        qs = Subject.objects.filter(workspace_id=request.workspace_id, archived_at__isnull=True)
        if self._is_student_or_parent(request):
            qs = qs.filter(visibility=Visibility.PUBLISHED)
        return Response(SubjectSerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        from apps.content.models import Subject

        subject = Subject.objects.create(
            workspace_id=request.workspace_id,
            name=request.data.get("name", ""),
            grade_level=request.data.get("grade_level", ""),
            color=request.data.get("color", ""),
        )
        return Response(SubjectSerializer(subject).data, status=status.HTTP_201_CREATED)


class SubjectDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "PATCH": {"required_permission_key": PermissionKey.CONTENT_EDIT},
        "DELETE": {"owner_only": True},
    }

    def get(self, request: Request, pk: int) -> Response:
        from apps.content.models import Subject
        from apps.core.errors import NotFound
        try:
            subject = Subject.objects.get(id=pk, workspace_id=request.workspace_id, archived_at__isnull=True)
        except Subject.DoesNotExist:
            raise NotFound("Subject not found")
        return Response(SubjectSerializer(subject).data)

    def patch(self, request: Request, pk: int) -> Response:
        from apps.content.models import Subject
        from apps.core.errors import NotFound
        try:
            subject = Subject.objects.get(id=pk, workspace_id=request.workspace_id, archived_at__isnull=True)
        except Subject.DoesNotExist:
            raise NotFound("Subject not found")
        allowed = {"name", "grade_level", "color", "visibility"}
        for key in allowed:
            if key in request.data:
                setattr(subject, key, request.data[key])
        subject.save()
        return Response(SubjectSerializer(subject).data)

    def delete(self, request: Request, pk: int) -> Response:
        from apps.content.models import Subject
        from apps.enrollment.models import Enrollment
        from apps.core.errors import NotFound, Conflict
        from django.utils import timezone
        try:
            subject = Subject.objects.get(id=pk, workspace_id=request.workspace_id, archived_at__isnull=True)
        except Subject.DoesNotExist:
            raise NotFound("Subject not found")
        active_paid = Enrollment.objects.filter(
            workspace_id=request.workspace_id,
            enrollable_type="SUBJECT",
            enrollable_id=pk,
            status="ACTIVE",
        ).exists()
        if active_paid:
            raise Conflict(
                "Cannot archive a subject with active paid enrollments.",
                code="HAS_ACTIVE_PAID_ENROLLMENTS",
            )
        subject.archived_at = timezone.now()
        subject.save(update_fields=["archived_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.CONTENT_CREATE},
    }

    def _is_student_or_parent(self, request: Request) -> bool:
        from apps.workspaces.models import WorkspaceMembership
        try:
            m = WorkspaceMembership.objects.get(
                user=request.user, workspace_id=request.workspace_id
            )
            return m.role in _STUDENT_PARENT
        except Exception:  # noqa: BLE001
            return False

    def get(self, request: Request) -> Response:
        from apps.content.models import Course
        from apps.core.enums import Visibility
        qs = Course.objects.filter(workspace_id=request.workspace_id, archived_at__isnull=True)
        if self._is_student_or_parent(request):
            qs = qs.filter(visibility=Visibility.PUBLISHED)
        return Response(CourseSerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        from apps.content.models import Course
        from apps.core import audit

        ser = CourseWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        course = Course.objects.create(
            workspace_id=request.workspace_id,
            **ser.validated_data,
        )
        audit.record(
            actor_id=request.user.id,
            action="COURSE_CREATED",
            target_type="Course",
            target_id=course.id,
            workspace_id=request.workspace_id,
            after={"title": course.title},
        )
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "PATCH": {"required_permission_key": PermissionKey.CONTENT_EDIT},
        "DELETE": {"owner_only": True},
    }

    def get(self, request: Request, pk: int) -> Response:
        from apps.content.models import Course
        from apps.core.errors import NotFound
        try:
            course = Course.objects.get(id=pk, workspace_id=request.workspace_id)
        except Course.DoesNotExist:
            raise NotFound("Course not found")
        return Response(CourseSerializer(course).data)

    def patch(self, request: Request, pk: int) -> Response:
        from apps.content.models import Course
        from apps.core.errors import NotFound
        from apps.core import audit
        try:
            course = Course.objects.get(id=pk, workspace_id=request.workspace_id)
        except Course.DoesNotExist:
            raise NotFound("Course not found")
        ser = CourseWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for attr, val in ser.validated_data.items():
            setattr(course, attr, val)
        course.save()
        audit.record(
            actor_id=request.user.id,
            action="COURSE_UPDATED",
            target_type="Course",
            target_id=course.id,
            workspace_id=request.workspace_id,
        )
        return Response(CourseSerializer(course).data)

    def delete(self, request: Request, pk: int) -> Response:
        from apps.content.models import Course
        from apps.core.errors import NotFound
        from django.utils import timezone
        try:
            course = Course.objects.get(id=pk, workspace_id=request.workspace_id)
        except Course.DoesNotExist:
            raise NotFound("Course not found")
        course.archived_at = timezone.now()
        course.save(update_fields=["archived_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LessonListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.CONTENT_CREATE},
    }

    def _is_student_or_parent(self, request: Request) -> bool:
        from apps.workspaces.models import WorkspaceMembership
        try:
            m = WorkspaceMembership.objects.get(
                user=request.user, workspace_id=request.workspace_id
            )
            return m.role in _STUDENT_PARENT
        except Exception:  # noqa: BLE001
            return False

    def get(self, request: Request, course_id: int) -> Response:
        from apps.content.models import Lesson, Course
        from apps.core.enums import Visibility
        # Students/parents may only list lessons of PUBLISHED courses
        if self._is_student_or_parent(request):
            try:
                course = Course.objects.get(
                    id=course_id,
                    workspace_id=request.workspace_id,
                    visibility=Visibility.PUBLISHED,
                )
            except Course.DoesNotExist:
                from apps.core.errors import NotFound
                raise NotFound("Course not found")
            _ = course  # confirm access
        qs = Lesson.objects.filter(
            workspace_id=request.workspace_id,
            parent_type="COURSE",
            parent_id=course_id,
            archived_at__isnull=True,
        ).order_by("order")
        return Response(LessonSerializer(qs, many=True).data)

    def post(self, request: Request, course_id: int) -> Response:
        from apps.content.models import Lesson
        lesson = Lesson.objects.create(
            workspace_id=request.workspace_id,
            parent_type="COURSE",
            parent_id=course_id,
            title=request.data.get("title", ""),
            order=request.data.get("order", 0),
            is_free_preview=request.data.get("is_free_preview", False),
        )
        return Response(LessonSerializer(lesson).data, status=status.HTTP_201_CREATED)


class LessonContentView(APIView):
    """
    GET /api/v1/lessons/{id}/content/ — return signed URLs for lesson content items.

    Access gate (REQ-ENR-CONTENT-01):
      - Staff may always access content in their workspace.
      - Students and parents are checked via lesson_accessible().
    File gate: files with scan_status INFECTED are blocked; PENDING blocks with 202.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
    }

    def get(self, request: Request, pk: int) -> Response:
        from apps.content.models import Lesson, LessonContent
        from apps.core.errors import NotFound, PermissionDeniedError
        from apps.core.enums import ScanStatus
        from apps.workspaces.models import WorkspaceMembership

        try:
            lesson = Lesson.objects.get(id=pk, workspace_id=request.workspace_id, archived_at__isnull=True)
        except Lesson.DoesNotExist:
            raise NotFound("Lesson not found.")

        # Access check for students/parents
        try:
            m = WorkspaceMembership.objects.get(user=request.user, workspace_id=request.workspace_id)
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if m.role in ("STUDENT", "PARENT"):
            from apps.enrollment.services.access import check_lesson_access
            from apps.core.errors import ValidationFailed
            student_id = request.user.id
            if m.role == "PARENT":
                from apps.parents.models import ParentStudentLink
                explicit_sid = request.query_params.get("student_id")
                links_qs = ParentStudentLink.objects.filter(
                    workspace_id=request.workspace_id,
                    parent_id=request.user.id,
                    unlinked_at__isnull=True,
                )
                child_ids = list(links_qs.values_list("student_id", flat=True))
                if not child_ids:
                    raise PermissionDeniedError("No linked student found.")
                if explicit_sid:
                    sid = int(explicit_sid)
                    if sid not in child_ids:
                        raise NotFound("Student not linked to this parent.")
                    student_id = sid
                elif len(child_ids) == 1:
                    student_id = child_ids[0]
                else:
                    raise ValidationFailed(
                        "?student_id= is required when a parent has more than one child.",
                        code="VALIDATION_FAILED",
                    )
            check_lesson_access(
                workspace_id=request.workspace_id,
                student_id=student_id,
                lesson_id=pk,
                user=request.user,
            )

        contents = LessonContent.objects.filter(
            lesson=lesson, workspace_id=request.workspace_id
        ).order_by("order")

        result = []
        for item in contents:
            entry = {
                "id": item.id,
                "content_type": item.content_type,
                "order": item.order,
                "body": item.body,
                "duration_seconds": item.duration_seconds,
                "url": None,
                "scan_status": None,
            }
            if item.file_id:
                from apps.files.models import StoredFile
                from apps.core.errors import ValidationFailed as VF
                try:
                    f = StoredFile.objects.get(id=item.file_id, workspace_id=request.workspace_id)
                    entry["scan_status"] = f.scan_status
                    if f.scan_status == ScanStatus.INFECTED:
                        entry["url"] = None
                    elif f.scan_status == ScanStatus.PENDING:
                        entry["url"] = None
                    else:
                        from apps.files.services.storage import get_presigned_url
                        entry["url"] = get_presigned_url(f.key)
                except StoredFile.DoesNotExist:
                    pass
            result.append(entry)

        return Response({"lesson_id": pk, "contents": result})
