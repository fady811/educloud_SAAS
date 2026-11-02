"""
Add partial UNIQUE constraint on student_course_accesses for non-revoked rows.

Without this, concurrent approvals create duplicate non-revoked rows and the
.get() in check_lesson_access raises MultipleObjectsReturned (→ 500).

The existing unique_together (workspace, student_id, course) covers the full
table. This partial constraint is the safety net for the non-revoked path only.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0002_lesson_parent_type_check"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="studentcourseaccess",
            constraint=models.UniqueConstraint(
                condition=models.Q(revoked_at__isnull=True),
                fields=["workspace_id", "student_id", "course_id"],
                name="sca_workspace_student_course_active_uniq",
            ),
        ),
    ]
