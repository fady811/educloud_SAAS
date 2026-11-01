"""Celery application, queue definitions and beat schedule (§20.2)."""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("educloud")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# Queues
# ---------------------------------------------------------------------------

default_exchange = Exchange("default", type="direct")
high_exchange = Exchange("high", type="direct")
files_exchange = Exchange("files", type="direct")

app.conf.task_queues = [
    Queue("default", default_exchange, routing_key="default"),
    Queue("high", high_exchange, routing_key="high"),
    Queue("files", files_exchange, routing_key="files"),
]
app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

# ---------------------------------------------------------------------------
# Beat schedule (§20.3)
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    # Workspace lifecycle sweeps
    "expire-grace-period": {
        "task": "apps.workspaces.tasks.expire_grace_period_workspaces",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "release-stale-subdomains": {
        "task": "apps.workspaces.tasks.release_stale_subdomains",
        "schedule": crontab(minute=30, hour=3),  # 3:30 AM Cairo
    },
    "purge-expired-workspaces": {
        "task": "apps.workspaces.tasks.purge_expired_workspaces",
        "schedule": crontab(minute=0, hour=4),   # 4:00 AM Cairo
    },
    # Subscription/addon expiry
    "expire-addons": {
        "task": "apps.billing.tasks.expire_addons",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "expire-subscriptions": {
        "task": "apps.billing.tasks.expire_subscriptions",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    # Payment sweeps
    "flag-overdue-payments": {
        "task": "apps.payments.tasks.flag_overdue_payments",
        "schedule": crontab(minute=0, hour=6),   # 6:00 AM Cairo
    },
    "remind-pending-payments": {
        "task": "apps.payments.tasks.remind_pending_payments",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "expire-monthly-course-access": {
        "task": "apps.payments.tasks.expire_monthly_course_access",
        "schedule": crontab(minute=0, hour=7),   # 7:00 AM Cairo
    },
    # Exam auto-submit
    "auto-submit-expired-attempts": {
        "task": "apps.assessments.tasks.auto_submit_expired_attempts",
        "schedule": crontab(minute="*/2"),  # every 2 min
    },
    # File cleanup
    "sweep-orphaned-files": {
        "task": "apps.files.tasks.sweep_orphaned_files",
        "schedule": crontab(minute=0, hour=2, day_of_week=0),  # weekly Sunday 2 AM
    },
    "verify-stored-files-sample": {
        "task": "apps.files.tasks.verify_stored_files_sample",
        "schedule": crontab(minute=0, hour=5),   # 5:00 AM Cairo
    },
    # Billing task moved to billing app; student payment sweeps in payments app
    "expire-billing-flag-overdue": {
        "task": "apps.billing.tasks.flag_overdue_payments",
        "schedule": crontab(minute=30, hour=6),  # 6:30 AM Cairo — distinct from payments sweep
    },
}
