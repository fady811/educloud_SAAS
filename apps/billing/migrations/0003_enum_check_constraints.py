"""Add CHECK constraints for all enum/choice fields on billing models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_snapshot_trigger"),
    ]

    operations = [
        # Subscription.status
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["SCHEDULED", "ACTIVE", "EXPIRED", "CANCELLED", "SUPERSEDED"]),
                name="billing_sub_status_valid",
            ),
        ),
        # SubscriptionPayment.kind
        migrations.AddConstraint(
            model_name="subscriptionpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=["NEW_SUBSCRIPTION", "RENEWAL", "UPGRADE", "ADDON"]),
                name="billing_subpay_kind_valid",
            ),
        ),
        # SubscriptionPayment.status
        migrations.AddConstraint(
            model_name="subscriptionpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED"]),
                name="billing_subpay_status_valid",
            ),
        ),
        # CapacityAddon.addon_type
        migrations.AddConstraint(
            model_name="capacityaddon",
            constraint=models.CheckConstraint(
                condition=models.Q(addon_type__in=["STUDENT_SLOTS", "STORAGE_GB"]),
                name="billing_addon_type_valid",
            ),
        ),
        # CapacityAddon.status
        migrations.AddConstraint(
            model_name="capacityaddon",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "ACTIVE", "EXPIRED", "CANCELLED"]),
                name="billing_addon_status_valid",
            ),
        ),
    ]
