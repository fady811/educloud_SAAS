"""Add CHECK constraints for all enum/choice fields on assessments models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0002_examattempt_version"),
    ]

    operations = [
        # Exam.status
        migrations.AddConstraint(
            model_name="exam",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["DRAFT", "PUBLISHED", "CLOSED"]),
                name="assess_exam_status_valid",
            ),
        ),
        # Question.question_type
        migrations.AddConstraint(
            model_name="question",
            constraint=models.CheckConstraint(
                condition=models.Q(question_type__in=["MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY"]),
                name="assess_q_type_valid",
            ),
        ),
        # ExamAttempt.status
        migrations.AddConstraint(
            model_name="examattempt",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["IN_PROGRESS", "SUBMITTED", "GRADED"]),
                name="assess_attempt_status_valid",
            ),
        ),
    ]
