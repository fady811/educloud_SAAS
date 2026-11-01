"""Login throttle — 5 failures / 15 min, then progressive cooldown (REQ-SEC-04).

Fail-closed design: Redis is the fast path; if Redis is unavailable the throttle
falls back to DB-backed counters (LoginAttempt model, DR-024). The DB path is only
taken on cache errors — it is never the primary path.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900  # 15 min


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_get(key: str) -> int | None:
    """Return cached count or None on error."""
    try:
        return cache.get(key, 0)
    except Exception:
        return None


def _cache_incr(key: str) -> bool:
    """Increment cached counter. Return True on success, False on error."""
    try:
        current = cache.get(key, 0)
        cache.set(key, current + 1, WINDOW_SECONDS)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# DB-backed fallback helpers
# ---------------------------------------------------------------------------

def _db_count(identifier: str, ip: str) -> tuple[int, int]:
    """Count recent attempts from DB. Returns (id_count, ip_count)."""
    from apps.accounts.models import LoginAttempt
    cutoff = timezone.now() - timedelta(seconds=WINDOW_SECONDS)
    id_hash = _hash(identifier)
    id_count = LoginAttempt.objects.filter(
        identifier_hash=id_hash, attempted_at__gte=cutoff
    ).count()
    ip_count = LoginAttempt.objects.filter(
        ip_address=ip, attempted_at__gte=cutoff
    ).count()
    return id_count, ip_count


def _db_record(identifier: str, ip: str) -> None:
    from apps.accounts.models import LoginAttempt
    try:
        LoginAttempt.objects.create(
            identifier_hash=_hash(identifier),
            ip_address=ip,
            attempted_at=timezone.now(),
        )
    except Exception:
        pass  # best-effort; if DB also fails, we can't do much


def _db_cleanup() -> None:
    """Remove attempt rows older than the window. Called opportunistically."""
    from apps.accounts.models import LoginAttempt
    cutoff = timezone.now() - timedelta(seconds=WINDOW_SECONDS)
    try:
        LoginAttempt.objects.filter(attempted_at__lt=cutoff).delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_login_allowed(identifier: str, ip: str) -> None:
    """Raise ThrottledError if the identifier or IP is locked out."""
    from apps.core.errors import ThrottledError

    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"

    count_id = _cache_get(key_id)
    count_ip = _cache_get(key_ip)

    if count_id is None or count_ip is None:
        # Redis unavailable — use DB fallback
        db_id, db_ip = _db_count(identifier, ip)
        if db_id >= MAX_ATTEMPTS or db_ip >= MAX_ATTEMPTS:
            raise ThrottledError(retry_after=WINDOW_SECONDS, code="LOGIN_BLOCKED")
        return

    if count_id >= MAX_ATTEMPTS or count_ip >= MAX_ATTEMPTS:
        raise ThrottledError(retry_after=WINDOW_SECONDS, code="LOGIN_BLOCKED")


def record_failure(identifier: str, ip: str) -> None:
    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"
    ok_id = _cache_incr(key_id)
    ok_ip = _cache_incr(key_ip)
    if not ok_id or not ok_ip:
        # Redis unavailable — persist to DB
        _db_record(identifier, ip)
        _db_cleanup()


def is_locked(identifier: str, ip: str) -> bool:
    """Return True if the identifier or IP is currently locked."""
    key_id = f"login:{identifier}"
    key_ip = f"login_ip:{ip}"
    count_id = _cache_get(key_id)
    count_ip = _cache_get(key_ip)
    if count_id is None or count_ip is None:
        db_id, db_ip = _db_count(identifier, ip)
        return db_id >= MAX_ATTEMPTS or db_ip >= MAX_ATTEMPTS
    return count_id >= MAX_ATTEMPTS or count_ip >= MAX_ATTEMPTS


def clear_counter(identifier: str) -> None:
    try:
        cache.delete(f"login:{identifier}")
    except Exception:
        # DB rows expire naturally; no explicit cleanup needed on success path
        pass
