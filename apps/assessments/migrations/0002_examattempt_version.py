"""Add version field to ExamAttempt for optimistic-concurrency autosave."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="examattempt",
            name="version",
            field=models.IntegerField(default=0),
        ),
    ]
