from rest_framework import serializers
from apps.billing.models import Package, Subscription, SubscriptionPayment, CapacityAddon

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ["id", "name", "slug", "description", "price_egp", "duration_months",
                  "max_students", "storage_gb", "max_subjects_courses", "max_groups",
                  "max_team_members", "display_order"]

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "package", "status", "starts_at", "ends_at", "entitlement_snapshot",
                  "proration_credit_egp"]

class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPayment
        fields = ["id", "subscription", "kind", "amount_egp", "status", "proof_file_id",
                  "submitted_at", "reviewed_at", "rejection_reason"]

class CapacityAddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacityAddon
        fields = ["id", "addon_type", "quantity", "status", "price_egp", "expires_at"]
