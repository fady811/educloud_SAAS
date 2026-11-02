"""
Add COURSE to LessonParentType and enforce it with a CHECK constraint.

Part 3.1 fix: lessons.parent_type had no COURSE value and no CHECK constraint,
so invalid values could be written silently.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lesson",
            name="parent_type",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("COURSE", "Course"),
                    ("WEEK", "Week"),
                    ("SECTION", "Section"),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.CheckConstraint(
                condition=models.Q(parent_type__in=["COURSE", "WEEK", "SECTION"]),
                name="lesson_parent_type_valid",
            ),
        ),
    ]
