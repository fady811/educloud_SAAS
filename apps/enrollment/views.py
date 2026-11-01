"""Enrollment views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission, ALL_MEMBERS
from apps.accounts.enums import PermissionKey
from apps.enrollment.serializers import EnrollmentSerializer, EnrollmentWriteSerializer


class EnrollmentListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        # Any member may list enrollments
        "GET": {"allowed_roles": ALL_MEMBERS},
        # POST: any member passes this gate; fine-grained check is in post() below
        "POST": {"allowed_roles": ALL_MEMBERS},
    }

    def get(self, request: Request) -> Response:
        from apps.enrollment.models import Enrollment
        student_id = request.query_params.get("student_id")
        qs = Enrollment.objects.filter(workspace_id=request.workspace_id)
        if student_id:
            qs = qs.filter(student_id=student_id)
        return Response(EnrollmentSerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        from apps.enrollment.models import Enrollment
        from apps.core import audit
        from apps.core.errors import Conflict, PermissionDeniedError, NotFound, ValidationFailed
        from apps.core.enums import Role, LimitKey
        from apps.workspaces.models import WorkspaceMembership
        from apps.accounts.services.permissions import has_permission
        from apps.billing.services.entitlements import check_limit

        ser = EnrollmentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        target_student_id = ser.validated_data["student_id"]

        # Resolve caller's membership
        try:
            caller_membership = WorkspaceMembership.objects.get(
                user=request.user, workspace_id=request.workspace_id
            )
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if caller_membership.role == Role.STUDENT:
            # Students may only enrol themselves
            if target_student_id != request.user.id:
                raise PermissionDeniedError(
                    "Students may only create enrollments for themselves."
                )
        else:
            # Non-students need STUDENT_EDIT permission
            if not caller_membership.is_owner and not has_permission(
                request.user, request.workspace_id, PermissionKey.STUDENT_EDIT
            ):
                raise PermissionDeniedError(
                    "You do not have permission to enroll students."
                )

        # Verify target student is a workspace member with STUDENT role
        try:
            target_membership = WorkspaceMembership.objects.get(
                user_id=target_student_id, workspace_id=request.workspace_id
            )
        except WorkspaceMembership.DoesNotExist:
            raise NotFound("Student not found in this workspace.")

        if target_membership.role != Role.STUDENT:
            raise ValidationFailed("Target user is not a student in this workspace.")

        # Check workspace student limit before creating the enrollment
        current_student_count = WorkspaceMembership.objects.filter(
            workspace_id=request.workspace_id, role=Role.STUDENT
        ).count()
        check_limit(request.workspace_id, LimitKey.MAX_STUDENTS, current_student_count)

        try:
            enrollment = Enrollment.objects.create(
                workspace_id=request.workspace_id,
                enrolled_by_id=request.user.id,
                **ser.validated_data,
            )
        except Exception:
            raise Conflict("Student already enrolled")

        audit.record(
            actor_id=request.user.id,
            action="STUDENT_ENROLLED",
            target_type="Enrollment",
            target_id=enrollment.id,
            workspace_id=request.workspace_id,
            after=ser.validated_data,
        )
        return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)


class EnrollmentDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        # Only staff with STUDENT_EDIT may cancel/delete an enrollment
        "DELETE": {"required_permission_key": PermissionKey.STUDENT_EDIT},
    }

    def _get(self, request, pk):
        from apps.enrollment.models import Enrollment
        from apps.core.errors import NotFound
        try:
            return Enrollment.objects.get(id=pk, workspace_id=request.workspace_id)
        except Enrollment.DoesNotExist:
            raise NotFound("Enrollment not found")

    def get(self, request: Request, pk: int) -> Response:
        return Response(EnrollmentSerializer(self._get(request, pk)).data)

    def delete(self, request: Request, pk: int) -> Response:
        from apps.core import audit
        from django.utils import timezone
        enrollment = self._get(request, pk)
        enrollment.unenrolled_at = timezone.now()
        enrollment.status = "CANCELLED"
        enrollment.save(update_fields=["unenrolled_at", "status"])
        audit.record(
            actor_id=request.user.id,
            action="STUDENT_UNENROLLED",
            target_type="Enrollment",
            target_id=enrollment.id,
            workspace_id=request.workspace_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
