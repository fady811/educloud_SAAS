from .base import *  # noqa: F403, F401

DEBUG = True
SECRET_KEY = "local-dev-secret-key-not-for-production"

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "educloud",
        "USER": "educloud",
        "PASSWORD": "educloud",
        "HOST": "localhost",
        "PORT": "5432",
        "ATOMIC_REQUESTS": False,
    }
}

CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/0",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CELERY_BROKER_URL = "redis://localhost:6379/1"
CELERY_RESULT_BACKEND = "redis://localhost:6379/2"
CELERY_TASK_ALWAYS_EAGER = False  # use real worker locally

STORAGE_BACKEND = "local"
SCANNER_BACKEND = "null"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://localhost:\d+$", r"^http://127\.0\.0\.1:\d+$"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

BASE_DOMAIN = "localhost"
WORKSPACE_DOMAIN_SUFFIX = ".localhost"
