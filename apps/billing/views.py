"""Billing views — packages, subscriptions, subscription payments, upgrades, addons."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from apps.billing.models import CapacityAddon, Package, Subscription, SubscriptionPayment
from apps.billing.serializers import (
    CapacityAddonSerializer,
    PackageSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionSerializer,
)
from apps.billing.services.subscriptions import create_subscription, get_upgrade_quote, prorate_upgrade, purchase_addon
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


class UpgradeOptionsView(APIView):
    """GET /billing/upgrade-options/ — list packages the current subscription can upgrade to."""
    permission_classes = [IsWorkspaceOwner]

    def get(self, request):
        from apps.core.enums import SubscriptionStatus

        active_sub = Subscription.objects.filter(
            workspace_id=request.workspace_id,
            status=SubscriptionStatus.ACTIVE,
        ).select_related("package").first()

        if not active_sub:
            return Response({"detail": "No active subscription found."}, status=status.HTTP_404_NOT_FOUND)

        packages = Package.objects.filter(
            is_active=True,
            price_egp__gt=active_sub.package.price_egp,
        ).order_by("price_egp")

        return Response({
            "current_subscription_id": active_sub.id,
            "current_package": PackageSerializer(active_sub.package).data,
            "upgradeable_packages": PackageSerializer(packages, many=True).data,
        })


class UpgradeQuoteView(APIView):
    """POST /billing/upgrade-quote/ — compute proration quote without committing."""
    permission_classes = [IsWorkspaceOwner]

    def post(self, request):
        from apps.core.errors import ValidationFailed

        subscription_id = request.data.get("subscription_id")
        package_id = request.data.get("package_id")
        if not subscription_id or not package_id:
            raise ValidationFailed("subscription_id and package_id are required.")

        quote = get_upgrade_quote(int(subscription_id), int(package_id))
        return Response(quote)


class UpgradeView(APIView):
    """POST /billing/upgrades/ — execute the upgrade."""
    permission_classes = [IsWorkspaceOwner]

    def post(self, request):
        from apps.core.errors import ValidationFailed

        subscription_id = request.data.get("subscription_id")
        package_id = request.data.get("package_id")
        quoted_amount_raw = request.data.get("quoted_amount_egp")
        if not subscription_id or not package_id:
            raise ValidationFailed("subscription_id and package_id are required.")

        quoted_amount = None
        if quoted_amount_raw is not None:
            try:
                quoted_amount = Decimal(str(quoted_amount_raw))
            except InvalidOperation:
                raise ValidationFailed("quoted_amount_egp must be a valid decimal.")

        new_sub = prorate_upgrade(
            int(subscription_id),
            int(package_id),
            actor_id=request.user.id,
            quoted_amount=quoted_amount,
        )
        return Response(SubscriptionSerializer(new_sub).data, status=status.HTTP_201_CREATED)


class AddonViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """GET /billing/addons/ — list capacity add-ons; POST — purchase one."""
    permission_classes = [IsWorkspaceOwner]
    serializer_class = CapacityAddonSerializer

    def get_queryset(self):
        return CapacityAddon.objects.filter(workspace_id=self.request.workspace_id).order_by("-created_at")

    def create(self, request):
        from apps.core.errors import ValidationFailed

        addon_type = request.data.get("addon_type")
        quantity = request.data.get("quantity")
        price_egp = request.data.get("price_egp")
        proof_file_id = request.data.get("proof_file_id")

        if not addon_type or not quantity or not price_egp:
            raise ValidationFailed("addon_type, quantity, and price_egp are required.")

        try:
            qty = int(quantity)
            price = Decimal(str(price_egp))
        except (ValueError, InvalidOperation):
            raise ValidationFailed("quantity must be an integer and price_egp a decimal.")

        addon = purchase_addon(
            workspace_id=request.workspace_id,
            addon_type=addon_type,
            quantity=qty,
            price_egp=price,
            proof_file_id=int(proof_file_id) if proof_file_id else None,
            actor_id=request.user.id,
        )
        return Response(CapacityAddonSerializer(addon).data, status=status.HTTP_201_CREATED)
