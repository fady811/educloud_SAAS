"""Parents views."""
from __future__ import annotations

import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission, STAFF_ONLY, PARENT_ONLY, STUDENT_ONLY
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
        from apps.core.errors import Conflict, ValidationFailed, PermissionDeniedError
        from apps.workspaces.models import WorkspaceMembership
        from apps.core.enums import Role

        # Inline guard: PARENT and STUDENT roles may never create links
        try:
            m = WorkspaceMembership.objects.get(
                user=request.user, workspace_id=request.workspace_id
            )
            if m.role in (Role.PARENT, Role.STUDENT):
                raise PermissionDeniedError("You do not have permission to create parent links.")
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

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


class StudentLinkingCodeView(APIView):
    """
    POST /students/{student_id}/linking-code/
    A student (or staff with STUDENT_EDIT) generates a single-use code that
    a parent can redeem to link themselves to this student.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"allowed_roles": STUDENT_ONLY},
    }

    def post(self, request: Request, student_id: int) -> Response:
        from apps.parents.models import ParentLinkCode
        from apps.workspaces.models import WorkspaceMembership
        from apps.core.enums import Role
        from apps.core.errors import PermissionDeniedError

        # Students may only generate codes for themselves
        try:
            m = WorkspaceMembership.objects.get(
                user=request.user, workspace_id=request.workspace_id
            )
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if m.role == Role.STUDENT and request.user.id != student_id:
            raise PermissionDeniedError("You may only generate a linking code for yourself.")

        expires_at = timezone.now() + datetime.timedelta(minutes=ParentLinkCode.TTL_MINUTES)
        code_obj = ParentLinkCode.objects.create(
            workspace_id=request.workspace_id,
            student_id=student_id,
            expires_at=expires_at,
        )
        return Response(
            {
                "code": code_obj.code,
                "expires_at": code_obj.expires_at.isoformat(),
                "ttl_minutes": ParentLinkCode.TTL_MINUTES,
            },
            status=status.HTTP_201_CREATED,
        )


class RedeemLinkingCodeView(APIView):
    """
    POST /parent-links/redeem/
    A parent submits a linking code to link themselves to the student who created it.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"allowed_roles": PARENT_ONLY},
    }

    def post(self, request: Request) -> Response:
        from apps.parents.models import ParentLinkCode, ParentStudentLink
        from apps.core.errors import ValidationFailed, Conflict
        from django.db import transaction

        code_str = request.data.get("code")
        if not code_str:
            raise ValidationFailed("code is required.")

        with transaction.atomic():
            try:
                code_obj = ParentLinkCode.objects.select_for_update().get(
                    code=code_str,
                    workspace_id=request.workspace_id,
                )
            except ParentLinkCode.DoesNotExist:
                raise ValidationFailed("Invalid or expired code.")

            now = timezone.now()
            if code_obj.expires_at < now:
                raise ValidationFailed("Code has expired.")
            if code_obj.redeemed_at is not None:
                raise Conflict("Code has already been redeemed.", code="CODE_ALREADY_USED")

            # Mark redeemed
            code_obj.redeemed_at = now
            code_obj.redeemed_by_id = request.user.id
            code_obj.save(update_fields=["redeemed_at", "redeemed_by_id", "updated_at"])

            # Create the link (idempotent)
            link, created = ParentStudentLink.objects.get_or_create(
                workspace_id=request.workspace_id,
                parent_id=request.user.id,
                student_id=code_obj.student_id,
                defaults={"relationship": ""},
            )
            if not created and link.unlinked_at is not None:
                link.unlinked_at = None
                link.save(update_fields=["unlinked_at"])

        return Response(
            ParentStudentLinkSerializer(link).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
