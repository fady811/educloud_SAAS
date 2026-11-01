from rest_framework import serializers
from apps.payments.models import StudentPayment, PaymentEvent, RefundRequest, WorkspacePaymentMethod

class StudentPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentPayment
        fields = ["id", "student", "payment_model", "amount_egp", "status", "source",
                  "proof_file_id", "submitted_at", "reviewed_at", "enrollable_type",
                  "enrollable_id", "period_start", "period_end"]

class WorkspacePaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspacePaymentMethod
        fields = ["id", "method", "display_name", "instructions", "is_active"]

class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = ["id", "payment", "amount_egp", "reason", "status", "reviewed_at"]
