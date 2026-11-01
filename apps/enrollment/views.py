"""Enrollment views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsWorkspaceMember
from apps.enrollment.serializers import EnrollmentSerializer, EnrollmentWriteSerializer


class EnrollmentListCreateView(APIView):
    permission_classes = [IsWorkspaceMember]

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
        from apps.core.errors import Conflict

        ser = EnrollmentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
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
    permission_classes = [IsWorkspaceMember]

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
