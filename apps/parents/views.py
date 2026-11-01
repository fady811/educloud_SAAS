"""Parents views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission, STAFF_ONLY, PARENT_ONLY
from apps.accounts.enums import PermissionKey
from apps.parents.serializers import ParentStudentLinkSerializer


class ParentLinkView(APIView):
    """
    Create/remove a parent↔student link.
    Only staff with STUDENT_EDIT permission may create links.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"required_permission_key": PermissionKey.STUDENT_EDIT},
        "DELETE": {"required_permission_key": PermissionKey.STUDENT_EDIT},
    }

    def post(self, request: Request) -> Response:
        from apps.parents.models import ParentStudentLink
        from apps.core.errors import Conflict, ValidationFailed

        parent_id = request.data.get("parent_id")
        student_id = request.data.get("student_id")

        if not parent_id or not student_id:
            raise ValidationFailed("parent_id and student_id are required.")

        link, created = ParentStudentLink.objects.get_or_create(
            workspace_id=request.workspace_id,
            parent_id=parent_id,
            student_id=student_id,
            defaults={"relationship": request.data.get("relationship", "")},
        )
        if not created:
            raise Conflict("Link already exists")
        return Response(ParentStudentLinkSerializer(link).data, status=status.HTTP_201_CREATED)

    def delete(self, request: Request) -> Response:
        from apps.parents.models import ParentStudentLink
        from apps.core.errors import NotFound
        from django.utils import timezone

        parent_id = request.data.get("parent_id")
        student_id = request.data.get("student_id")
        link = ParentStudentLink.objects.filter(
            workspace_id=request.workspace_id,
            parent_id=parent_id,
            student_id=student_id,
            unlinked_at__isnull=True,
        ).first()
        if not link:
            raise NotFound("Link not found")
        link.unlinked_at = timezone.now()
        link.save(update_fields=["unlinked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ParentStudentsView(APIView):
    """
    Get students linked to the authenticated parent user.
    A parent can ONLY see their own children.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": PARENT_ONLY},
    }

    def get(self, request: Request) -> Response:
        from apps.parents.models import ParentStudentLink

        # Hard-code parent_id = request.user.id — no user-supplied override allowed
        links = ParentStudentLink.objects.filter(
            workspace_id=request.workspace_id,
            parent_id=request.user.id,
            unlinked_at__isnull=True,
        )
        return Response(ParentStudentLinkSerializer(links, many=True).data)
