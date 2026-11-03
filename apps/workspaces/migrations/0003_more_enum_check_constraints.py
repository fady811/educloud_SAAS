"""Add CHECK constraints for remaining enum columns in workspaces app."""
from django.db import migrations, models

_WS_STATUSES = ["SETUP", "PENDING_PAYMENT", "PENDING_APPROVAL", "ACTIVE",
                "GRACE_PERIOD", "FROZEN", "DEACTIVATED", "DELETED"]


class Migration(migrations.Migration):

    dependencies = [
        ("workspaces", "0002_enum_check_constraints"),
    ]

    operations = [
        # Workspace.status
        migrations.AddConstraint(
            model_name="workspace",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=_WS_STATUSES),
                name="ws_status_valid",
            ),
        ),
        # Workspace.deactivation_cause (nullable — allow NULL)
        migrations.AddConstraint(
            model_name="workspace",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(deactivation_cause__isnull=True)
                    | models.Q(deactivation_cause__in=["NON_PAYMENT", "ADMIN_ACTION"])
                ),
                name="ws_deactivation_cause_valid",
            ),
        ),
        # WorkspaceStatusHistory.from_status / to_status
        migrations.AddConstraint(
            model_name="workspacestatushistory",
            constraint=models.CheckConstraint(
                condition=models.Q(from_status__in=_WS_STATUSES),
                name="ws_log_from_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspacestatushistory",
            constraint=models.CheckConstraint(
                condition=models.Q(to_status__in=_WS_STATUSES),
                name="ws_log_to_status_valid",
            ),
        ),
        # CustomDomain.status
        migrations.AddConstraint(
            model_name="customdomain",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["PENDING_DNS", "VERIFYING", "ACTIVE", "FAILED", "DETACHED"]),
                name="ws_domain_status_valid",
            ),
        ),
    ]
