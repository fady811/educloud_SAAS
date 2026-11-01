"""Wire the prevent_snapshot_mutation trigger onto billing_subscriptions (INV-27)."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
        ("core", "0002_audit_idempotency"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER enforce_snapshot_immutability
            BEFORE UPDATE ON billing_subscriptions
            FOR EACH ROW
            EXECUTE FUNCTION prevent_snapshot_mutation();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS enforce_snapshot_immutability ON billing_subscriptions;
            """,
        ),
    ]
