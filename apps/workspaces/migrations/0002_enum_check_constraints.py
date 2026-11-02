"""
Add CHECK constraints on enum columns in workspaces app.

Fixes the role="OWNER" bug class: Django choices= is not enforced at the DB
level, so invalid values can be written silently via objects.create().
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="workspacemembership",
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=[
                    "SUPER_ADMIN", "TEACHER", "TEAM_MEMBER", "STUDENT", "PARENT"
                ]),
                name="wm_role_valid",
            ),
        ),
    ]
