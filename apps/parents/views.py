"""Parents views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsWorkspaceMember
from apps.parents.serializers import ParentStudentLinkSerializer


class ParentLinkView(APIView):
    """
    Create/remove a parent↔student link.
    Only a workspace owner/teacher (permission STUDENT_MANAGE) may create links.
    A parent cannot link themselves to an arbitrary student_id they don't already own.
    """
    permission_classes = [IsWorkspaceMember]

    def post(self, request: Request) -> Response:
        from apps.parents.models import ParentStudentLink
        from apps.accounts.services.permissions import has_permission
        from apps.accounts.enums import PermissionKey
        from apps.core.errors import Conflict, PermissionDeniedError

        # Only staff (owner/teacher with explicit grant) may create parent links
        if not has_permission(request.user, request.workspace_id, PermissionKey.STUDENT_EDIT):
            raise PermissionDeniedError("You do not have permission to manage parent links.")

        parent_id = request.data.get("parent_id")
        student_id = request.data.get("student_id")

        if not parent_id or not student_id:
            from apps.core.errors import ValidationFailed
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
        from apps.accounts.services.permissions import has_permission
        from apps.accounts.enums import PermissionKey
        from apps.core.errors import NotFound, PermissionDeniedError
        from django.utils import timezone

        if not has_permission(request.user, request.workspace_id, PermissionKey.STUDENT_EDIT):
            raise PermissionDeniedError("You do not have permission to manage parent links.")

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
    A parent can ONLY see their own children — enforced by filtering on request.user.id.
    """
    permission_classes = [IsWorkspaceMember]

    def get(self, request: Request) -> Response:
        from apps.parents.models import ParentStudentLink

        # Hard-code parent_id = request.user.id — no user-supplied override allowed
        links = ParentStudentLink.objects.filter(
            workspace_id=request.workspace_id,
            parent_id=request.user.id,
            unlinked_at__isnull=True,
        )
        return Response(ParentStudentLinkSerializer(links, many=True).data)
