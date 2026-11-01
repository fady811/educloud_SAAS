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

    def get(self, request: Request) -> Response:
        from apps.content.models import Subject
        qs = Subject.objects.filter(workspace_id=request.workspace_id, archived_at__isnull=True)
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
