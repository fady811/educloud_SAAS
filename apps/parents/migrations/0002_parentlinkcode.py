"""Add ParentLinkCode for self-service parent linking (Part 5.1)."""
from django.db import migrations, models
import apps.parents.models


class Migration(migrations.Migration):

    dependencies = [
        ("parents", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParentLinkCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("workspace_id", models.BigIntegerField(db_index=True)),
                ("student_id", models.BigIntegerField()),
                ("code", models.CharField(default=apps.parents.models._generate_code, max_length=32, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("redeemed_at", models.DateTimeField(blank=True, null=True)),
                ("redeemed_by_id", models.BigIntegerField(blank=True, null=True)),
            ],
            options={
                "db_table": "parent_link_codes",
                "app_label": "parents",
            },
        ),
        migrations.AddIndex(
            model_name="parentlinkcode",
            index=models.Index(fields=["code"], name="plc_code_idx"),
        ),
        migrations.AddIndex(
            model_name="parentlinkcode",
            index=models.Index(fields=["workspace_id", "student_id"], name="plc_student_idx"),
        ),
    ]
