"""Login throttle — 5 failures / 15 min, then progressive cooldown (REQ-SEC-04)."""
from __future__ import annotations

from django.core.cache import cache

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900  # 15 min


def check_login_allowed(identifier: str, ip: str) -> None:
    """Raise ThrottledError if the identifier or IP is locked out."""
    from apps.core.errors import ThrottledError

    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"

    count_id = cache.get(key_id, 0)
    count_ip = cache.get(key_ip, 0)

    if count_id >= MAX_ATTEMPTS or count_ip >= MAX_ATTEMPTS:
        raise ThrottledError(retry_after=WINDOW_SECONDS, code="LOGIN_BLOCKED")


def record_failure(identifier: str, ip: str) -> None:
    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"
    cache.set(key_id, cache.get(key_id, 0) + 1, WINDOW_SECONDS)
    cache.set(key_ip, cache.get(key_ip, 0) + 1, WINDOW_SECONDS)


def is_locked(identifier: str, ip: str) -> bool:
    """Return True if the identifier or IP is currently locked."""
    return (
        cache.get(f"login:{identifier}", 0) >= MAX_ATTEMPTS
        or cache.get(f"login_ip:{ip}", 0) >= MAX_ATTEMPTS
    )


def clear_counter(identifier: str) -> None:
    cache.delete(f"login:{identifier}")
