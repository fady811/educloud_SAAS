"""
Create audit_logs (no FKs) and idempotency_keys tables, plus the immutability triggers (§12.7).
"""
from django.db import migrations, models


AUDIT_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs rows are immutable (DR-038)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_immutable
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
"""

AUDIT_TRIGGER_REVERSE_SQL = """
DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;
DROP FUNCTION IF EXISTS prevent_audit_log_mutation();
"""

SNAPSHOT_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION prevent_snapshot_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.entitlement_snapshot IS NOT NULL AND NEW.entitlement_snapshot <> OLD.entitlement_snapshot THEN
        RAISE EXCEPTION 'entitlement_snapshot is immutable after it is set (INV-27)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

SNAPSHOT_TRIGGER_REVERSE_SQL = """
DROP FUNCTION IF EXISTS prevent_snapshot_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0001_extensions")]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("workspace_id", models.BigIntegerField(null=True, blank=True, db_index=True)),
                ("actor_id", models.BigIntegerField(null=True, blank=True)),
                ("actor_type", models.CharField(max_length=20, default="USER")),
                ("action", models.CharField(max_length=100, db_index=True)),
                ("target_type", models.CharField(max_length=100, db_index=True)),
                ("target_id", models.CharField(max_length=255, blank=True, default="")),
                ("before", models.JSONField(default=dict)),
                ("after", models.JSONField(default=dict)),
                ("reason", models.TextField(blank=True, default="")),
                ("request_id", models.CharField(max_length=64, blank=True, default="", db_index=True)),
                ("created_at", models.DateTimeField(db_index=True)),
            ],
            options={"db_table": "audit_logs", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="AuditLog",
            index=models.Index(fields=["workspace_id", "-created_at"], name="audit_ws_time_idx"),
        ),
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key_hash", models.CharField(max_length=64, unique=True, db_index=True)),
                ("result_status", models.SmallIntegerField()),
                ("result_body", models.JSONField(default=dict)),
                ("expires_at", models.DateTimeField()),
            ],
            options={"db_table": "idempotency_keys"},
        ),
        migrations.RunSQL(AUDIT_TRIGGER_SQL, reverse_sql=AUDIT_TRIGGER_REVERSE_SQL),
        migrations.RunSQL(SNAPSHOT_TRIGGER_SQL, reverse_sql=SNAPSHOT_TRIGGER_REVERSE_SQL),
    ]
