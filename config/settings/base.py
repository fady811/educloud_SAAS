"""
EduCloud LMS — Base settings (§23).
All configuration is read from the environment. No module reads os.environ directly (§7.10).
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"Required environment variable {key!r} is not set.")
    return val or ""


def _bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("1", "true", "yes")


def _int(key: str, default: int) -> int:
    return int(_env(key, str(default)))


def _decimal(key: str, default: str) -> Decimal:
    return Decimal(_env(key, default))


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = _env("SECRET_KEY", required=True)
DEBUG = _bool("DEBUG", False)
ENVIRONMENT = _env("ENVIRONMENT", "production")

# All domain values derive from BASE_DOMAIN (INV-114a, §15.1).
BASE_DOMAIN = _env("BASE_DOMAIN", "educloud.app")
WORKSPACE_DOMAIN_SUFFIX = f".{BASE_DOMAIN}"

ALLOWED_HOSTS: list[str] = [h.strip() for h in _env("ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS += [f".{BASE_DOMAIN}", BASE_DOMAIN]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core",
    "apps.workspaces",
    "apps.accounts",
    "apps.notifications",
    "apps.billing",
    "apps.files",
    "apps.content",
    "apps.groups",
    "apps.enrollment",
    "apps.assessments",
    "apps.payments",
    "apps.communication",
    "apps.parents",
    "apps.reports",
    "apps.support",
    "apps.adminconsole",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.tenancy.middleware.TenantResolverMiddleware",
    "apps.core.middleware.ReadOnlyWorkspaceMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"  # No Channels routing; present for runtime only.

# ---------------------------------------------------------------------------
# Templates (minimal — API-only backend)
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

import dj_database_url  # type: ignore[import-untyped]  # optional helper

_db_url = _env("DATABASE_URL", "postgres://educloud:educloud@localhost:5432/educloud")
DATABASES = {
    "default": dj_database_url.parse(_db_url, conn_max_age=600, conn_health_checks=True),
}
DATABASES["default"]["OPTIONS"] = {"options": "-c search_path=public"}

# Disable ATOMIC_REQUESTS — services own transactions (§7.6).
# ATOMIC_REQUESTS is False by default; stated explicitly as a reminder.
DATABASES["default"]["ATOMIC_REQUESTS"] = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Caches / Redis
# ---------------------------------------------------------------------------

REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailOrPhoneAuthBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # legacy-hash upgrade path
]

# ---------------------------------------------------------------------------
# Sessions (DB-backed; §15.2, REQ-NFR-05)
# ---------------------------------------------------------------------------

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = f".{BASE_DOMAIN}"
SESSION_COOKIE_AGE = _int("SESSION_COOKIE_AGE", 86400)
SESSION_SAVE_EVERY_REQUEST = False

# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

CSRF_COOKIE_HTTPONLY = False  # frontend JS needs to read it
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [f"https://*.{BASE_DOMAIN}", f"https://{BASE_DOMAIN}"]

# ---------------------------------------------------------------------------
# CORS (§15.1)
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGIN_REGEXES = [
    rf"^https://[\w-]+\.{BASE_DOMAIN.replace('.', r'\.')}$",
    rf"^https://{BASE_DOMAIN.replace('.', r'\.')}$",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_HEADERS = [
    "accept", "authorization", "content-type", "x-csrftoken",
    "x-request-id", "idempotency-key",
]

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # Default-deny: views without an explicit permission class will fail.
        # This default is intentionally restrictive; override per view.
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "apps.core.filters.AllowlistedOrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.errors.exception_handler",
    # Money: NUMERIC fields serialized as strings (REQ-NFR-09).
    "COERCE_DECIMAL_TO_STRING": True,
    # Rate limiting (§18.7)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": _env("API_THROTTLE_RATE", "100/hour"),
        "user": _env("API_THROTTLE_RATE", "1000/hour"),
        "registration": "10/hour",
        "password_reset": "3/hour",
        "subdomain_check": "30/minute",
        "invite_link": "20/minute",
    },
    # Trusted reverse proxies in front of Gunicorn.
    # Set to 1 when a single nginx/load-balancer proxy is in the chain so that
    # DRF's get_ident() reads the correct client IP from X-Forwarded-For and
    # ignores client-supplied entries that would otherwise allow throttle bypass.
    # Set to 0 to always use REMOTE_ADDR (no proxy). Never leave as None (default)
    # in production — None trusts the full X-Forwarded-For header unconditionally.
    "NUM_PROXIES": _int("NUM_PROXIES", 1),
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "EduCloud LMS API",
    "DESCRIPTION": "Backend API for EduCloud LMS — Egyptian tutoring platform.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# Celery (§20.2)
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = _env("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = _env("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Cairo"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# INV-112a: visibility_timeout must exceed longest expected task (video compression ~1h)
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": _int("CELERY_VISIBILITY_TIMEOUT", 43200),
}
CELERY_TASK_ROUTES = {
    "apps.*.tasks.*": {"queue": "default"},
    "apps.files.tasks.*": {"queue": "files"},
    "apps.accounts.tasks.*": {"queue": "high"},
    "apps.notifications.tasks.*": {"queue": "default"},
}
CELERY_TASK_QUEUES = None  # defined in config/celery.py

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = _env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = _env("EMAIL_HOST", "localhost")
EMAIL_PORT = _int("EMAIL_PORT", 587)
EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = _env("DEFAULT_FROM_EMAIL", f"noreply@{BASE_DOMAIN}")

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "ar"       # Arabic (CON-01)
TIME_ZONE = "Africa/Cairo" # REQ-NFR-08
USE_I18N = True
USE_TZ = True              # All timestamps UTC-aware; displayed in Africa/Cairo

# ---------------------------------------------------------------------------
# Storage (§5.15, §11.5)
# ---------------------------------------------------------------------------

STORAGE_BACKEND = _env("STORAGE_BACKEND", "r2")  # r2 | local

# R2 / S3 credentials
R2_ACCOUNT_ID = _env("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = _env("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = _env("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = _env("R2_BUCKET_NAME", "educloud-dev")
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else ""

# Local storage (dev/test)
LOCAL_STORAGE_ROOT = BASE_DIR / "media"
LOCAL_STORAGE_URL = "/media/"

# Upload limits (§5.15.2)
UPLOAD_SIZE_LIMIT_MB = _int("DEFAULT_UPLOAD_SIZE_LIMIT_MB", 500)
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/webm", "video/quicktime"]
ALLOWED_DOCUMENT_TYPES = ["application/pdf"]
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
# SVG rejected (DR-041, INV-95a)
ALLOWED_ATTACHMENT_TYPES = ALLOWED_DOCUMENT_TYPES + ALLOWED_IMAGE_TYPES + [
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
SIGNED_URL_TTL_CONTENT = 7200      # 2h for lesson content (§18.5)
SIGNED_URL_TTL_PROOF = 900         # 15 min for payment proofs (REQ-SEC-10)

# Video compression threshold (§5.15.4)
VIDEO_COMPRESSION_BITRATE_THRESHOLD_KBPS = 4000

# ---------------------------------------------------------------------------
# Virus scanning
# ---------------------------------------------------------------------------

SCANNER_BACKEND = _env("SCANNER_BACKEND", "null")  # clamav | null | eicar_only
CLAMAV_HOST = _env("CLAMAV_HOST", "127.0.0.1")
CLAMAV_PORT = _int("CLAMAV_PORT", 3310)
SCANNER_CALLBACK_SECRET = _env("SCANNER_CALLBACK_SECRET", "")

# ---------------------------------------------------------------------------
# Security settings (§18)
# ---------------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Tokens
# Login throttle policy (REQ-SEC-04) — consumed by apps.accounts.views.LoginThrottle.
# 5 attempts per 15-minute sliding window, per client IP.
LOGIN_THROTTLE_MAX_ATTEMPTS = _int("LOGIN_THROTTLE_MAX_ATTEMPTS", 5)
LOGIN_THROTTLE_WINDOW_SECONDS = _int("LOGIN_THROTTLE_WINDOW_SECONDS", 900)

PASSWORD_RESET_TIMEOUT = _int("PASSWORD_RESET_TIMEOUT", 3600)
VERIFICATION_TOKEN_EXPIRY = _int("VERIFICATION_TOKEN_EXPIRY", 86400)
INVITE_LINK_EXPIRY_DAYS = 14
TEAM_INVITE_EXPIRY_DAYS = 7
LINKING_CODE_EXPIRY_DAYS = 14

# Session limits per role (REQ-SEC-07)
SESSION_LIMITS = {
    "STUDENT": 3,
    "PARENT": 3,
    "TEACHER": 5,
    "TEAM_MEMBER": 5,
    "SUPER_ADMIN": 10,
}

# ---------------------------------------------------------------------------
# Business rules (operator-adjustable; stored in DB for workspace-level overrides)
# ---------------------------------------------------------------------------

DEFAULT_GRACE_PERIOD_DAYS = _int("DEFAULT_GRACE_PERIOD_DAYS", 7)
DEFAULT_RETENTION_DAYS = _int("DEFAULT_RETENTION_DAYS", 90)
SUBDOMAIN_RESERVATION_DAYS = 30

UPGRADE_MIN_CHARGE_EGP = _decimal("UPGRADE_MIN_CHARGE_EGP", "1.00")
UPGRADE_MIN_REMAINING_DAYS = _int("UPGRADE_MIN_REMAINING_DAYS", 3)
PENDING_PAYMENT_REMINDER_INTERVAL_HOURS = _int("PENDING_PAYMENT_REMINDER_INTERVAL_HOURS", 48)

# CSV import row limit
CSV_IMPORT_ROW_LIMIT = 1000

# Export row cap (§5.12)
EXPORT_ROW_CAP = 10_000

# ---------------------------------------------------------------------------
# Logging (§21, structlog)
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "structlog.stdlib.ProcessorFormatter",
            "processor": "structlog.processors.JSONRenderer",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------

SENTRY_DSN = _env("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk  # type: ignore[import-untyped]
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        # Scrub sensitive data (§21.4)
        before_send=lambda event, hint: event,
    )

# ---------------------------------------------------------------------------
# Metrics facade (DR-040, INV-117)
# ---------------------------------------------------------------------------
METRICS_BACKEND = _env("METRICS_BACKEND", "noop")  # noop | prometheus
