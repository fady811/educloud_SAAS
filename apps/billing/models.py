"""Billing models: Package, Subscription, SubscriptionPayment, CapacityAddon."""
from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.core.enums import (
    AddonStatus,
    AddonType,
    SubPaymentKind,
    SubPaymentStatus,
    SubscriptionStatus,
)
from apps.core.models import TimeStampedModel, TenantModel
from apps.core.validators import validate_hex_color


class Package(TimeStampedModel):
    """EduCloud subscription plan (REQ-SUB-01)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    price_egp = models.DecimalField(max_digits=12, decimal_places=2)
    duration_months = models.SmallIntegerField(default=1)
    max_students = models.IntegerField(null=True, blank=True)
    storage_gb = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_subjects_courses = models.IntegerField(null=True, blank=True)
    max_groups = models.IntegerField(null=True, blank=True)
    max_team_members = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.SmallIntegerField(default=0)

    class Meta:
        app_label = "billing"
        db_table = "billing_packages"
        ordering = ["display_order"]

    def __str__(self) -> str:
        return f"{self.name} ({self.price_egp} EGP/{self.duration_months}mo)"


class Subscription(TenantModel):
    """
    The live entitlement record for a workspace (REQ-SUB-02).
    INV-27: entitlement_snapshot is immutable once set (enforced by DB trigger).
    """

    package = models.ForeignKey("billing.Package", on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.SCHEDULED, db_index=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(db_index=True)
    entitlement_snapshot = models.JSONField(null=True, blank=True)
    # Proration support (DR-036/DR-037)
    previous_subscription_id = models.BigIntegerField(null=True, blank=True)
    proration_credit_egp = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        app_label = "billing"
        db_table = "billing_subscriptions"
        indexes = [
            models.Index(fields=["workspace", "status"], name="sub_ws_status_idx"),
            models.Index(fields=["ends_at"], name="sub_ends_at_idx"),
        ]

    def __str__(self) -> str:
        return f"Subscription#{self.pk} ws={self.workspace_id} {self.status}"


class SubscriptionPayment(TenantModel):
    """Manual payment record (REQ-SUB-05, teacher→EduCloud)."""

    subscription = models.ForeignKey("billing.Subscription", on_delete=models.CASCADE, related_name="payments")
    kind = models.CharField(max_length=20, choices=SubPaymentKind.choices)
    amount_egp = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=SubPaymentStatus.choices, default=SubPaymentStatus.SUBMITTED, db_index=True)
    proof_file_id = models.BigIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_id = models.BigIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        app_label = "billing"
        db_table = "billing_subscription_payments"
        indexes = [
            models.Index(fields=["workspace", "status"], name="subpay_ws_status_idx"),
        ]


class CapacityAddon(TenantModel):
    """One-time capacity top-up (REQ-SUB-15)."""

    addon_type = models.CharField(max_length=20, choices=AddonType.choices)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=AddonStatus.choices, default=AddonStatus.PENDING)
    price_egp = models.DecimalField(max_digits=12, decimal_places=2)
    proof_file_id = models.BigIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "billing"
        db_table = "billing_capacity_addons"
        indexes = [
            models.Index(fields=["workspace", "addon_type", "status"], name="addon_ws_type_idx"),
        ]
