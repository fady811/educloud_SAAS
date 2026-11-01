from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identifier_hash", models.CharField(max_length=64)),
                ("ip_address", models.CharField(max_length=45)),
                ("attempted_at", models.DateTimeField()),
            ],
            options={
                "db_table": "login_attempts",
                "app_label": "accounts",
            },
        ),
        migrations.AddIndex(
            model_name="loginattempt",
            index=models.Index(fields=["identifier_hash", "attempted_at"], name="la_ident_at_idx"),
        ),
        migrations.AddIndex(
            model_name="loginattempt",
            index=models.Index(fields=["ip_address", "attempted_at"], name="la_ip_at_idx"),
        ),
    ]
