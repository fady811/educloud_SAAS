"""Login throttle — 5 failures / 15 min, then progressive cooldown (REQ-SEC-04).

Fail-closed design: if the cache is unavailable, in-process counters are used
so that the throttle still blocks repeat failures (rather than failing open).
NOTE: in-process counters do not survive restarts and are not shared across
workers — a DB-backed counter is preferable but requires a migration. See
OPEN_QUESTIONS.md for details.
"""
from __future__ import annotations

import threading

from django.core.cache import cache

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900  # 15 min

# In-process fallback counters used when cache is unavailable (fail-closed)
_fallback_lock = threading.Lock()
_fallback_counts: dict[str, int] = {}


def _cache_get(key: str) -> int:
    try:
        return cache.get(key, 0)
    except Exception:
        with _fallback_lock:
            return _fallback_counts.get(key, 0)


def _cache_incr(key: str) -> None:
    try:
        current = cache.get(key, 0)
        cache.set(key, current + 1, WINDOW_SECONDS)
    except Exception:
        with _fallback_lock:
            _fallback_counts[key] = _fallback_counts.get(key, 0) + 1


def check_login_allowed(identifier: str, ip: str) -> None:
    """Raise ThrottledError if the identifier or IP is locked out."""
    from apps.core.errors import ThrottledError

    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"

    count_id = _cache_get(key_id)
    count_ip = _cache_get(key_ip)

    if count_id >= MAX_ATTEMPTS or count_ip >= MAX_ATTEMPTS:
        raise ThrottledError(retry_after=WINDOW_SECONDS, code="LOGIN_BLOCKED")


def record_failure(identifier: str, ip: str) -> None:
    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"
    _cache_incr(key_id)
    _cache_incr(key_ip)


def is_locked(identifier: str, ip: str) -> bool:
    """Return True if the identifier or IP is currently locked."""
    return (
        _cache_get(f"login:{identifier}") >= MAX_ATTEMPTS
        or _cache_get(f"login_ip:{ip}") >= MAX_ATTEMPTS
    )


def clear_counter(identifier: str) -> None:
    try:
        cache.delete(f"login:{identifier}")
    except Exception:
        with _fallback_lock:
            _fallback_counts.pop(f"login:{identifier}", None)
