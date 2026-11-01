"""Student payment models (tracking only, no funds through EduCloud)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import (
    PaymentMethod,
    PaymentSource,
    PaymentStatusLink,
    RefundStatus,
    StudentPaymentModel,
    StudentPaymentStatus,
)
from apps.core.models import TenantModel


class WorkspacePaymentMethod(TenantModel):
    method = models.CharField(max_length=30, choices=PaymentMethod.choices)
    is_active = models.BooleanField(default=True)
    display_name = models.CharField(max_length=100)
    instructions = models.TextField(blank=True)
    account_details = models.JSONField(default=dict)

    class Meta:
        app_label = "payments"
        db_table = "payments_workspace_methods"


class StudentPayment(TenantModel):
    """Student→Teacher payment record (REQ-PAY-01; tracking only)."""

    student = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="student_payments")
    payment_model = models.CharField(max_length=20, choices=StudentPaymentModel.choices)
    amount_egp = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=StudentPaymentStatus.choices, default=StudentPaymentStatus.PENDING, db_index=True)
    source = models.CharField(max_length=20, choices=PaymentSource.choices, default=PaymentSource.TEACHER_DIRECT)
    payment_method = models.ForeignKey("payments.WorkspacePaymentMethod", on_delete=models.SET_NULL, null=True, blank=True)
    proof_file_id = models.BigIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_id = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # Link to enrollable
    enrollable_type = models.CharField(max_length=20, blank=True)
    enrollable_id = models.BigIntegerField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    status_link = models.CharField(max_length=20, choices=PaymentStatusLink.choices, blank=True)

    class Meta:
        app_label = "payments"
        db_table = "payments_student_payments"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "student", "status"], name="sp_student_status_idx"),
            models.Index(fields=["workspace", "status"], name="sp_ws_status_idx"),
        ]


class PaymentEvent(TenantModel):
    """Immutable audit trail of payment state changes."""

    payment = models.ForeignKey("payments.StudentPayment", on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    actor_id = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "payments"
        db_table = "payments_events"
        ordering = ["-created_at"]


class RefundRequest(TenantModel):
    payment = models.ForeignKey("payments.StudentPayment", on_delete=models.CASCADE, related_name="refunds")
    amount_egp = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.REQUESTED)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        app_label = "payments"
        db_table = "payments_refunds"
