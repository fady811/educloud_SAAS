"""Groups views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission, ALL_MEMBERS
from apps.accounts.enums import PermissionKey
from apps.groups.serializers import (
    GroupSerializer, GroupWriteSerializer, SessionSerializer, AttendanceSerializer,
)


class GroupListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.GROUP_CREATE},
    }

    def get(self, request: Request) -> Response:
        from apps.groups.models import Group
        qs = Group.objects.filter(workspace_id=request.workspace_id, archived_at__isnull=True)
        return Response(GroupSerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        from apps.groups.models import Group
        from apps.core import audit
        ser = GroupWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        group = Group.objects.create(workspace_id=request.workspace_id, **ser.validated_data)
        audit.record(
            actor_id=request.user.id,
            action="GROUP_CREATED",
            target_type="Group",
            target_id=group.id,
            workspace_id=request.workspace_id,
            after={"name": group.name},
        )
        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "PATCH": {"required_permission_key": PermissionKey.GROUP_EDIT},
        "DELETE": {"owner_only": True},
    }

    def _get(self, request, pk):
        from apps.groups.models import Group
        from apps.core.errors import NotFound
        try:
            return Group.objects.get(id=pk, workspace_id=request.workspace_id)
        except Group.DoesNotExist:
            raise NotFound("Group not found")

    def get(self, request: Request, pk: int) -> Response:
        return Response(GroupSerializer(self._get(request, pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        from apps.core import audit
        group = self._get(request, pk)
        ser = GroupWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for k, v in ser.validated_data.items():
            setattr(group, k, v)
        group.save()
        audit.record(
            actor_id=request.user.id, action="GROUP_UPDATED",
            target_type="Group", target_id=group.id, workspace_id=request.workspace_id,
        )
        return Response(GroupSerializer(group).data)

    def delete(self, request: Request, pk: int) -> Response:
        from django.utils import timezone
        group = self._get(request, pk)
        group.archived_at = timezone.now()
        group.save(update_fields=["archived_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupMemberView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"required_permission_key": PermissionKey.GROUP_ASSIGN},
        "DELETE": {"required_permission_key": PermissionKey.GROUP_ASSIGN},
    }

    def post(self, request: Request, group_id: int) -> Response:
        from apps.groups.models import GroupMembership, Group
        from apps.core.errors import NotFound, Conflict
        try:
            group = Group.objects.get(id=group_id, workspace_id=request.workspace_id)
        except Group.DoesNotExist:
            raise NotFound("Group not found")
        student_id = request.data.get("student_id")
        _, created = GroupMembership.objects.get_or_create(
            workspace_id=request.workspace_id,
            group=group,
            student_id=student_id,
        )
        if not created:
            raise Conflict("Student already in group")
        return Response({"group_id": group_id, "student_id": student_id}, status=status.HTTP_201_CREATED)

    def delete(self, request: Request, group_id: int) -> Response:
        from apps.groups.models import GroupMembership
        from apps.core.errors import NotFound
        from django.utils import timezone
        student_id = request.data.get("student_id")
        m = GroupMembership.objects.filter(
            workspace_id=request.workspace_id,
            group_id=group_id,
            student_id=student_id,
            removed_at__isnull=True,
        ).first()
        if not m:
            raise NotFound("Membership not found")
        m.removed_at = timezone.now()
        m.save(update_fields=["removed_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.ATTENDANCE_RECORD},
    }

    def get(self, request: Request, group_id: int) -> Response:
        from apps.groups.models import Session
        qs = Session.objects.filter(workspace_id=request.workspace_id, group_id=group_id)
        return Response(SessionSerializer(qs, many=True).data)

    def post(self, request: Request, group_id: int) -> Response:
        from apps.groups.models import Session
        session = Session.objects.create(
            workspace_id=request.workspace_id,
            group_id=group_id,
            title=request.data.get("title", ""),
            scheduled_at=request.data["scheduled_at"],
            duration_minutes=request.data.get("duration_minutes", 60),
        )
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


class AttendanceBulkView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"required_permission_key": PermissionKey.ATTENDANCE_RECORD},
    }

    def post(self, request: Request, session_id: int) -> Response:
        from apps.groups.models import Session, AttendanceRecord
        from apps.core.errors import NotFound
        try:
            session = Session.objects.get(id=session_id, workspace_id=request.workspace_id)
        except Session.DoesNotExist:
            raise NotFound("Session not found")
        records = request.data.get("records", [])
        result = []
        for r in records:
            ar, _ = AttendanceRecord.objects.update_or_create(
                workspace_id=request.workspace_id,
                session=session,
                student_id=r["student_id"],
                defaults={"status": r["status"], "notes": r.get("notes", ""), "recorded_by_id": request.user.id},
            )
            result.append(AttendanceSerializer(ar).data)
        return Response(result, status=status.HTTP_200_OK)
