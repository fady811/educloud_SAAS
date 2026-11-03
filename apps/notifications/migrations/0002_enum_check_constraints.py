"""Add CHECK constraints for all enum/choice fields on notifications models."""
from django.db import migrations, models

_NOTIFICATION_CATEGORIES = [
    "NEW_ANNOUNCEMENT", "EXAM_PUBLISHED", "GRADE_POSTED", "ASSIGNMENT_DUE",
    "PAYMENT_DUE_OR_OVERDUE", "ENROLLMENT_CONFIRMED", "GROUP_CHANGED",
    "SUBSCRIPTION_STATUS_CHANGED", "SUPPORT_TICKET_UPDATE",
]


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        # Notification.category
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.CheckConstraint(
                condition=models.Q(category__in=_NOTIFICATION_CATEGORIES),
                name="notif_category_valid",
            ),
        ),
        # NotificationPreference.category
        migrations.AddConstraint(
            model_name="notificationpreference",
            constraint=models.CheckConstraint(
                condition=models.Q(category__in=_NOTIFICATION_CATEGORIES),
                name="notifpref_category_valid",
            ),
        ),
    ]
