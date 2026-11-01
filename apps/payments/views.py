"""Student payment views — proof submission, approve, reject, refunds."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.core.permissions import WorkspacePermission, ALL_MEMBERS
from apps.accounts.enums import PermissionKey
from apps.payments.models import StudentPayment, WorkspacePaymentMethod, PaymentEvent
from apps.payments.serializers import StudentPaymentSerializer, WorkspacePaymentMethodSerializer


def _record_payment_event(payment: StudentPayment, from_status: str, actor_id: int, notes: str = "") -> None:
    PaymentEvent.objects.create(
        workspace_id=payment.workspace_id,
        payment=payment,
        from_status=from_status,
        to_status=payment.status,
        actor_id=actor_id,
        notes=notes,
    )


class StudentPaymentViewSet(ListModelMixin, RetrieveModelMixin, CreateModelMixin, GenericViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = StudentPaymentSerializer
    # GET: staff need PAYMENT_VIEW; students can see their own (filtered in get_queryset if needed)
    # POST: students create for themselves; owner/staff with PAYMENT_VIEW may create for any student
    # approve/reject actions are POST — permission checked inline
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.PAYMENT_VIEW},
        "POST": {"allowed_roles": ALL_MEMBERS},
        "DELETE": {"owner_only": True},
    }

    def get_queryset(self):
        from apps.core.enums import Role
        from apps.workspaces.models import WorkspaceMembership
        qs = StudentPayment.objects.filter(workspace_id=self.request.workspace_id)
        # Students see only their own payments
        try:
            m = WorkspaceMembership.objects.get(
                user=self.request.user, workspace_id=self.request.workspace_id
            )
            if m.role == Role.STUDENT:
                qs = qs.filter(student_id=self.request.user.id)
        except WorkspaceMembership.DoesNotExist:
            pass
        return qs

    def perform_create(self, serializer):
        from apps.core.errors import PermissionDeniedError
        from apps.core.enums import Role
        from apps.workspaces.models import WorkspaceMembership
        from apps.accounts.services.permissions import has_permission

        # Determine caller's role
        try:
            m = WorkspaceMembership.objects.get(
                user=self.request.user, workspace_id=self.request.workspace_id
            )
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if m.role == Role.STUDENT:
            # Students may only create payments for themselves
            student_id = serializer.validated_data.get(
                "student_id",
                getattr(serializer.validated_data.get("student"), "id", None),
            )
            if student_id is None:
                student_id = self.request.user.id
            if student_id != self.request.user.id:
                raise PermissionDeniedError("Students may only create payments for themselves.")
        else:
            # Staff need PAYMENT_VIEW to create a payment
            if not m.is_owner and not has_permission(
                self.request.user, self.request.workspace_id, PermissionKey.PAYMENT_VIEW
            ):
                raise PermissionDeniedError("You do not have permission to create student payments.")

        serializer.save(workspace_id=self.request.workspace_id)

    @action(detail=True, methods=["post"], url_path="submit-proof")
    def submit_proof(self, request, pk=None):
        """Student submits payment proof. PENDING → PENDING (with proof_file_id set)."""
        from apps.core.enums import StudentPaymentStatus
        from apps.core.errors import ValidationFailed

        proof_file_id = request.data.get("proof_file_id")
        if not proof_file_id:
            raise ValidationFailed("proof_file_id is required.")

        with transaction.atomic():
            payment = StudentPayment.objects.select_for_update().get(
                pk=pk, workspace_id=request.workspace_id
            )
            if payment.student_id != request.user.id:
                from apps.core.errors import PermissionDeniedError
                raise PermissionDeniedError("You can only submit proof for your own payments.")
            if payment.status != StudentPaymentStatus.PENDING:
                raise ValidationFailed(
                    f"Cannot submit proof for payment in status {payment.status}."
                )
            from_status = payment.status
            payment.proof_file_id = proof_file_id
            payment.submitted_at = timezone.now()
            payment.save(update_fields=["proof_file_id", "submitted_at", "updated_at"])
            _record_payment_event(payment, from_status, request.user.id, "Proof submitted")

        return Response(StudentPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Teacher/admin approves a student payment. PENDING → PAID."""
        from apps.core.enums import StudentPaymentStatus
        from apps.core.errors import ValidationFailed, PermissionDeniedError
        from apps.accounts.services.permissions import has_permission
        from apps.workspaces.models import WorkspaceMembership

        try:
            m = WorkspaceMembership.objects.get(user=request.user, workspace_id=request.workspace_id)
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if not m.is_owner and not has_permission(request.user, request.workspace_id, PermissionKey.PAYMENT_CONFIRM):
            raise PermissionDeniedError("You do not have permission to approve payments.")

        with transaction.atomic():
            payment = StudentPayment.objects.select_for_update().get(
                pk=pk, workspace_id=request.workspace_id
            )
            if payment.status != StudentPaymentStatus.PENDING:
                raise ValidationFailed(
                    f"Cannot approve payment in status {payment.status}."
                )
            from_status = payment.status
            payment.status = StudentPaymentStatus.PAID
            payment.reviewed_at = timezone.now()
            payment.reviewed_by_id = request.user.id
            notes = request.data.get("notes", "")
            if notes:
                payment.notes = notes
            payment.save(update_fields=["status", "reviewed_at", "reviewed_by_id", "notes", "updated_at"])
            _record_payment_event(payment, from_status, request.user.id, notes or "Approved")

        return Response(StudentPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Teacher/admin rejects a student payment. PENDING → REJECTED."""
        from apps.core.enums import StudentPaymentStatus
        from apps.core.errors import ValidationFailed, PermissionDeniedError
        from apps.accounts.services.permissions import has_permission
        from apps.workspaces.models import WorkspaceMembership

        reason = request.data.get("reason", "")
        if not reason:
            raise ValidationFailed("reason is required when rejecting a payment.")

        try:
            m = WorkspaceMembership.objects.get(user=request.user, workspace_id=request.workspace_id)
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if not m.is_owner and not has_permission(request.user, request.workspace_id, PermissionKey.PAYMENT_REJECT):
            raise PermissionDeniedError("You do not have permission to reject payments.")

        with transaction.atomic():
            payment = StudentPayment.objects.select_for_update().get(
                pk=pk, workspace_id=request.workspace_id
            )
            if payment.status != StudentPaymentStatus.PENDING:
                raise ValidationFailed(
                    f"Cannot reject payment in status {payment.status}."
                )
            from_status = payment.status
            payment.status = StudentPaymentStatus.REJECTED
            payment.reviewed_at = timezone.now()
            payment.reviewed_by_id = request.user.id
            payment.notes = reason
            payment.save(update_fields=["status", "reviewed_at", "reviewed_by_id", "notes", "updated_at"])
            _record_payment_event(payment, from_status, request.user.id, reason)

        return Response(StudentPaymentSerializer(payment).data)


class WorkspacePaymentMethodViewSet(ModelViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = WorkspacePaymentMethodSerializer
    # Billing configuration is owner-only (REQ-BILLING-04)
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"owner_only": True},
        "PUT": {"owner_only": True},
        "PATCH": {"owner_only": True},
        "DELETE": {"owner_only": True},
    }

    def get_queryset(self):
        return WorkspacePaymentMethod.objects.filter(workspace_id=self.request.workspace_id)

    def perform_create(self, serializer):
        serializer.save(workspace_id=self.request.workspace_id)
