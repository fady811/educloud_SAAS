"""Add visibility field to Subject with CHECK constraint."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0003_studentcourseaccess_partial_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="visibility",
            field=models.CharField(
                max_length=20,
                choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("ARCHIVED", "Archived")],
                default="DRAFT",
            ),
        ),
        migrations.AddConstraint(
            model_name="subject",
            constraint=models.CheckConstraint(
                condition=models.Q(visibility__in=["DRAFT", "PUBLISHED", "ARCHIVED"]),
                name="subject_visibility_valid",
            ),
        ),
    ]
