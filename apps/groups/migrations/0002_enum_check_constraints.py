"""Add CHECK constraints for all enum/choice fields on groups models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0001_initial"),
    ]

    operations = [
        # Group.status
        migrations.AddConstraint(
            model_name="group",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "FULL", "ARCHIVED"]),
                name="groups_status_valid",
            ),
        ),
        # Attendance.status
        migrations.AddConstraint(
            model_name="attendancerecord",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["PRESENT", "ABSENT", "LATE", "EXCUSED"]),
                name="groups_attendance_status_valid",
            ),
        ),
    ]
