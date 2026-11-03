"""Add CHECK constraints for all enum/choice fields on files models."""
from django.db import migrations, models

_FILE_CATEGORIES = [
    "LESSON_VIDEO", "LESSON_DOCUMENT", "LESSON_ATTACHMENT",
    "ASSIGNMENT_SUBMISSION", "PAYMENT_PROOF", "BRANDING_LOGO",
    "ANNOUNCEMENT_ATTACHMENT", "MESSAGE_ATTACHMENT",
]


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0001_initial"),
    ]

    operations = [
        # StoredFile.category
        migrations.AddConstraint(
            model_name="storedfile",
            constraint=models.CheckConstraint(
                condition=models.Q(category__in=_FILE_CATEGORIES),
                name="files_category_valid",
            ),
        ),
        # StoredFile.scan_status
        migrations.AddConstraint(
            model_name="storedfile",
            constraint=models.CheckConstraint(
                condition=models.Q(scan_status__in=["PENDING", "CLEAN", "INFECTED", "ERROR", "SKIPPED"]),
                name="files_scan_status_valid",
            ),
        ),
    ]
