"""Add CHECK constraints for all enum/choice fields on communication models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0001_initial"),
    ]

    operations = [
        # Announcement.scope
        migrations.AddConstraint(
            model_name="announcement",
            constraint=models.CheckConstraint(
                condition=models.Q(scope__in=["WORKSPACE", "SUBJECT", "COURSE", "GROUP"]),
                name="comm_scope_valid",
            ),
        ),
    ]
