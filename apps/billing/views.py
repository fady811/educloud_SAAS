"""Billing views — packages, subscriptions, subscription payments."""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from apps.billing.models import Package, Subscription, SubscriptionPayment
from apps.billing.serializers import (
    PackageSerializer,
    SubscriptionSerializer,
    SubscriptionPaymentSerializer,
)
from apps.billing.services.subscriptions import create_subscription
from apps.core.permissions import IsWorkspaceOwner, IsSuperAdmin


class PackageViewSet(ReadOnlyModelViewSet):
    queryset = Package.objects.filter(is_active=True)
    serializer_class = PackageSerializer
    permission_classes = []  # Public listing


class SubscriptionViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsWorkspaceOwner]
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return Subscription.objects.filter(
            workspace_id=self.request.workspace_id
        ).order_by("-created_at")

    @action(detail=False, methods=["post"])
    def subscribe(self, request):
        package_id = request.data.get("package_id")
        sub = create_subscription(
            workspace_id=request.workspace_id,
            package_id=package_id,
            actor_id=request.user.id,
        )
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)


class SubscriptionPaymentViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """
    Workspace owners submit proof; super-admins approve or reject.
    State machine: SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED
    On APPROVED, the linked subscription is activated.
    """
    permission_classes = [IsWorkspaceOwner]
    serializer_class = SubscriptionPaymentSerializer

    def get_queryset(self):
        return SubscriptionPayment.objects.filter(
            workspace_id=self.request.workspace_id
        ).order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="submit-proof")
    def submit_proof(self, request, pk=None):
        from django.db import transaction
        from django.utils import timezone
        from apps.core.enums import SubPaymentStatus
        from apps.core.errors import ValidationFailed

        proof_file_id = request.data.get("proof_file_id")
        if not proof_file_id:
            raise ValidationFailed("proof_file_id is required.")

        with transaction.atomic():
            payment = SubscriptionPayment.objects.select_for_update().get(
                pk=pk, workspace_id=request.workspace_id
            )
            if payment.status != SubPaymentStatus.SUBMITTED:
                raise ValidationFailed(
                    f"Cannot submit proof for payment in status {payment.status}."
                )
            payment.proof_file_id = proof_file_id
            payment.status = SubPaymentStatus.UNDER_REVIEW
            payment.submitted_at = timezone.now()
            payment.save(update_fields=["proof_file_id", "status", "submitted_at", "updated_at"])

        return Response(SubscriptionPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def approve(self, request, pk=None):
        """
        Super-admin approves a subscription payment → activates the subscription.
        UNDER_REVIEW → APPROVED, then activate_subscription().
        """
        from django.db import transaction
        from django.utils import timezone
        from apps.core.enums import SubPaymentStatus
        from apps.core.errors import ValidationFailed
        from apps.billing.services.subscriptions import activate_subscription
        from apps.core import audit

        with transaction.atomic():
            payment = SubscriptionPayment.objects.select_for_update().get(pk=pk)
            if payment.status != SubPaymentStatus.UNDER_REVIEW:
                raise ValidationFailed(
                    f"Cannot approve payment in status {payment.status}. Must be UNDER_REVIEW."
                )
            payment.status = SubPaymentStatus.APPROVED
            payment.reviewed_at = timezone.now()
            payment.reviewed_by_id = request.user.id
            payment.save(update_fields=["status", "reviewed_at", "reviewed_by_id", "updated_at"])

            audit.record(
                actor_id=request.user.id,
                actor_type="ADMIN",
                action="SUBSCRIPTION_PAYMENT_APPROVED",
                target_type="SubscriptionPayment",
                target_id=payment.id,
                workspace_id=payment.workspace_id,
                before={"status": SubPaymentStatus.UNDER_REVIEW},
                after={"status": SubPaymentStatus.APPROVED},
            )

            # Activate the linked subscription
            activate_subscription(payment.subscription_id, actor_id=request.user.id)

        return Response(SubscriptionPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def reject(self, request, pk=None):
        """
        Super-admin rejects a subscription payment.
        UNDER_REVIEW → REJECTED. Subscription stays SCHEDULED.
        """
        from django.db import transaction
        from django.utils import timezone
        from apps.core.enums import SubPaymentStatus
        from apps.core.errors import ValidationFailed
        from apps.core import audit

        reason = request.data.get("reason", "")
        if not reason:
            raise ValidationFailed("reason is required when rejecting a payment.")

        with transaction.atomic():
            payment = SubscriptionPayment.objects.select_for_update().get(pk=pk)
            if payment.status != SubPaymentStatus.UNDER_REVIEW:
                raise ValidationFailed(
                    f"Cannot reject payment in status {payment.status}. Must be UNDER_REVIEW."
                )
            payment.status = SubPaymentStatus.REJECTED
            payment.reviewed_at = timezone.now()
            payment.reviewed_by_id = request.user.id
            payment.rejection_reason = reason
            payment.save(update_fields=["status", "reviewed_at", "reviewed_by_id", "rejection_reason", "updated_at"])

            audit.record(
                actor_id=request.user.id,
                actor_type="ADMIN",
                action="SUBSCRIPTION_PAYMENT_REJECTED",
                target_type="SubscriptionPayment",
                target_id=payment.id,
                workspace_id=payment.workspace_id,
                before={"status": SubPaymentStatus.UNDER_REVIEW},
                after={"status": SubPaymentStatus.REJECTED, "reason": reason},
            )

        return Response(SubscriptionPaymentSerializer(payment).data)
