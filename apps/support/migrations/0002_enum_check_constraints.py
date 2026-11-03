"""Add CHECK constraints for all enum/choice fields on support models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        # SupportTicket.category
        migrations.AddConstraint(
            model_name="supportticket",
            constraint=models.CheckConstraint(
                condition=models.Q(category__in=["BILLING", "TECHNICAL", "ACCOUNT", "CONTENT", "OTHER"]),
                name="support_category_valid",
            ),
        ),
        # SupportTicket.status
        migrations.AddConstraint(
            model_name="supportticket",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]),
                name="support_status_valid",
            ),
        ),
    ]
