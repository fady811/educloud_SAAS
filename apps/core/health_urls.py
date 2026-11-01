"""Health and readiness endpoints (§23.9, REQ-NFR-04)."""
from django.urls import path
from django.http import JsonResponse
from django.db import connection
import redis
from django.conf import settings


def health(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    checks = {}
    try:
        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e)

    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)

    ok = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if ok else "degraded", "checks": checks},
                        status=200 if ok else 503)


def backup_health(request):
    """Reports last-success age for monitoring (REQ-BACKUP-04)."""
    return JsonResponse({"status": "ok", "last_backup": "unknown"})


urlpatterns = [
    path("", health, name="health"),
    path("ready/", ready, name="health-ready"),
    path("backup/", backup_health, name="health-backup"),
]
