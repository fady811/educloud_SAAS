"""Reports views (Tier 10 — real PostgreSQL aggregation queries)."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission
from apps.accounts.enums import PermissionKey


class AttendanceReportView(APIView):
    """
    Attendance breakdown per student and per status.
    Optional filters: group_id, student_id, date_from, date_to.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.ATTENDANCE_VIEW_REPORTS},
    }

    def get(self, request: Request) -> Response:
        from apps.groups.models import AttendanceRecord
        from django.db.models import Count

        qs = AttendanceRecord.objects.filter(workspace_id=request.workspace_id)

        group_id = request.query_params.get("group_id")
        student_id = request.query_params.get("student_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if group_id:
            qs = qs.filter(session__group_id=group_id)
        if student_id:
            qs = qs.filter(student_id=student_id)
        if date_from:
            qs = qs.filter(session__scheduled_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(session__scheduled_at__date__lte=date_to)

        by_student = list(
            qs.values("student_id", "status").annotate(count=Count("id")).order_by("student_id", "status")
        )
        totals = {
            row["status"]: row["total"]
            for row in qs.values("status").annotate(total=Count("id"))
        }

        return Response({"by_student": by_student, "totals": totals})


class PaymentReportView(APIView):
    """
    Payment summary by status with totals.
    Optional filters: student_id, payment_model, date_from, date_to.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.REPORTS_VIEW},
    }

    def get(self, request: Request) -> Response:
        from apps.payments.models import StudentPayment
        from django.db.models import Sum, Count

        qs = StudentPayment.objects.filter(workspace_id=request.workspace_id)

        student_id = request.query_params.get("student_id")
        payment_model = request.query_params.get("payment_model")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if student_id:
            qs = qs.filter(student_id=student_id)
        if payment_model:
            qs = qs.filter(payment_model=payment_model)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        by_status = list(
            qs.values("status").annotate(
                count=Count("id"),
                total_egp=Sum("amount_egp"),
            ).order_by("status")
        )
        paid_total = qs.filter(status="PAID").aggregate(total=Sum("amount_egp"))["total"] or 0

        return Response({
            "by_status": by_status,
            "paid_total_egp": str(paid_total),
        })


class EnrollmentReportView(APIView):
    """
    Enrollment counts by type and status.
    Optional filters: enrollable_type (GROUP | COURSE), status.
    """
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.REPORTS_VIEW},
    }

    def get(self, request: Request) -> Response:
        from apps.enrollment.models import Enrollment
        from django.db.models import Count

        qs = Enrollment.objects.filter(workspace_id=request.workspace_id)

        enrollable_type = request.query_params.get("enrollable_type")
        enroll_status = request.query_params.get("status")

        if enrollable_type:
            qs = qs.filter(enrollable_type=enrollable_type)
        if enroll_status:
            qs = qs.filter(status=enroll_status)

        by_type_status = list(
            qs.values("enrollable_type", "status").annotate(count=Count("id")).order_by("enrollable_type", "status")
        )
        total = qs.aggregate(total=Count("id"))["total"] or 0

        return Response({"by_type_status": by_type_status, "total": total})
