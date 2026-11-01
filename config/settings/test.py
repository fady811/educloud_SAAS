from .local import *  # noqa: F403, F401

# Celery: run tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Fast hashing in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Use null scanner and local storage in tests
SCANNER_BACKEND = "null"
STORAGE_BACKEND = "local"

# Disable debug toolbar in tests
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

# Suppress logging noise in tests
import logging
logging.disable(logging.CRITICAL)

# No email in tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable default throttling in tests (LoginThrottleTests exercises throttle directly)
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405

# Raise the IP-based LoginThrottle limit so matrix tests can log in many times without blocking
LOGIN_THROTTLE_MAX_ATTEMPTS = 10000

# Allow any host in tests (test client uses 'testserver' by default)
ALLOWED_HOSTS = ["*"]

# Use in-process cache for tests so Redis is not required
CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Database
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "educloud_test",
        "USER": "educloud",
        "PASSWORD": "educloud",
        "HOST": "localhost",
        "PORT": "5432",
        "ATOMIC_REQUESTS": False,
        "TEST": {"NAME": "educloud_test"},
    }
}
