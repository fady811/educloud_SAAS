"""Add CHECK constraints for remaining enum columns in content app."""
from django.db import migrations, models

_GRADE_LEVELS = [
    "PRIMARY_1", "PRIMARY_2", "PRIMARY_3", "PRIMARY_4", "PRIMARY_5", "PRIMARY_6",
    "PREP_1", "PREP_2", "PREP_3",
    "SEC_1", "SEC_2", "SEC_3",
    "OTHER",
]


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0004_subject_visibility"),
    ]

    operations = [
        # Subject.grade_level (nullable/blank — allow empty string)
        migrations.AddConstraint(
            model_name="subject",
            constraint=models.CheckConstraint(
                condition=models.Q(grade_level__in=["", *_GRADE_LEVELS]),
                name="subject_grade_level_valid",
            ),
        ),
        # Course.visibility
        migrations.AddConstraint(
            model_name="course",
            constraint=models.CheckConstraint(
                condition=models.Q(visibility__in=["DRAFT", "PUBLISHED", "ARCHIVED"]),
                name="course_visibility_valid",
            ),
        ),
        # Course.pricing_type
        migrations.AddConstraint(
            model_name="course",
            constraint=models.CheckConstraint(
                condition=models.Q(pricing_type__in=["FREE", "ONE_TIME", "MONTHLY"]),
                name="course_pricing_type_valid",
            ),
        ),
        # LessonContent.content_type
        migrations.AddConstraint(
            model_name="lessoncontent",
            constraint=models.CheckConstraint(
                condition=models.Q(content_type__in=["VIDEO", "PDF", "TEXT", "EXTERNAL_LINK", "FILE_SET"]),
                name="lesson_content_type_valid",
            ),
        ),
    ]
