"""Add CHECK constraints for all enum/choice fields on payments models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_alter_studentpayment_ordering"),
    ]

    operations = [
        # WorkspacePaymentMethod.method
        migrations.AddConstraint(
            model_name="workspacepaymentmethod",
            constraint=models.CheckConstraint(
                condition=models.Q(method__in=["VODAFONE_CASH", "INSTAPAY", "FAWRY", "BANK_TRANSFER", "CASH", "OTHER"]),
                name="payments_method_valid",
            ),
        ),
        # StudentPayment.payment_model
        migrations.AddConstraint(
            model_name="studentpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(payment_model__in=["WORKSPACE_MONTHLY", "COURSE_ONE_TIME", "COURSE_MONTHLY"]),
                name="payments_sp_model_valid",
            ),
        ),
        # StudentPayment.status
        migrations.AddConstraint(
            model_name="studentpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PAID", "PARTIALLY_PAID", "OVERDUE", "REJECTED", "DISPUTED", "REFUNDED"]),
                name="payments_sp_status_valid",
            ),
        ),
        # StudentPayment.source
        migrations.AddConstraint(
            model_name="studentpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(source__in=["STUDENT_SUBMITTED", "TEACHER_DIRECT"]),
                name="payments_sp_source_valid",
            ),
        ),
        # StudentPayment.status_link (nullable blank — allow empty string)
        migrations.AddConstraint(
            model_name="studentpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(status_link__in=["", "NOT_REQUIRED", "PENDING", "PAID", "WAIVED", "OVERDUE"]),
                name="payments_sp_status_link_valid",
            ),
        ),
    ]
