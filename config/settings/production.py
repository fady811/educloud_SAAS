"""Production settings — fails fast on missing required variables (§23.10)."""
import os
from .base import *  # noqa: F403, F401

# Fail fast on missing required variables
_REQUIRED = [
    "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "BASE_DOMAIN",
    "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME",
    "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND",
    "DEFAULT_FROM_EMAIL",
]
for _var in _REQUIRED:
    if not os.environ.get(_var):
        raise RuntimeError(f"[PRODUCTION] Required env var {_var!r} is not set.")

DEBUG = False
STORAGE_BACKEND = "r2"

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
