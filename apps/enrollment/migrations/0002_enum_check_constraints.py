"""Add CHECK constraints for all enum/choice fields on enrollment models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0001_initial"),
    ]

    operations = [
        # Enrollment.enrollable_type
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.CheckConstraint(
                condition=models.Q(enrollable_type__in=["SUBJECT", "COURSE"]),
                name="enrl_enrollable_type_valid",
            ),
        ),
        # Enrollment.status
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "SUSPENDED", "COMPLETED", "CANCELLED", "EXPIRED"]),
                name="enrl_status_valid",
            ),
        ),
    ]
