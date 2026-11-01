"""Session management (REQ-SEC-05/06/07)."""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.utils import timezone

from apps.core.enums import Role


def create_session(
    request: object,
    user: "User",  # type: ignore[name-defined]
    workspace_id: int | None = None,
) -> None:
    """Record a session row and enforce the per-role concurrent session limit."""
    from django.contrib.auth import login
    from apps.accounts.models import UserSession
    from apps.workspaces.models import WorkspaceMembership

    # Determine role for limit lookup
    role = "SUPER_ADMIN" if user.is_super_admin else Role.TEACHER
    if workspace_id:
        membership = WorkspaceMembership.objects.filter(user=user, workspace_id=workspace_id).first()
        if membership:
            role = membership.role

    limit = settings.SESSION_LIMITS.get(role, 3)
    _enforce_session_limit(user, workspace_id, limit)

    # Perform Django login (creates the session record)
    login(request, user)

    session_key = getattr(request.session, "session_key", None)
    if session_key:
        session_hash = hashlib.sha256(session_key.encode()).hexdigest()
        UserSession.objects.update_or_create(
            session_key_hash=session_hash,
            defaults={
                "user": user,
                "workspace_id": workspace_id,
                "device_info": _parse_device(request),
                "ip_address": _get_ip(request),
                "revoked_at": None,
            },
        )


def revoke_session(request: object, session_id: int, user: "User") -> None:  # type: ignore[name-defined]
    from apps.accounts.models import UserSession
    from django.contrib.sessions.backends.db import SessionStore

    session = UserSession.objects.get(id=session_id, user=user)
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])
    # Invalidate the Django session
    try:
        store = SessionStore(session_key=None)
        store.delete()
    except Exception:  # noqa: BLE001
        pass


def revoke_others(request: object, user: "User") -> None:  # type: ignore[name-defined]
    from apps.accounts.models import UserSession

    current_key = getattr(request.session, "session_key", None)
    current_hash = hashlib.sha256(current_key.encode()).hexdigest() if current_key else ""
    UserSession.objects.filter(user=user, revoked_at__isnull=True).exclude(
        session_key_hash=current_hash
    ).update(revoked_at=timezone.now())


def _enforce_session_limit(user: "User", workspace_id: int | None, limit: int) -> None:  # type: ignore[name-defined]
    from apps.accounts.models import UserSession

    active_sessions = list(
        UserSession.objects.filter(
            user=user,
            workspace_id=workspace_id,
            revoked_at__isnull=True,
        ).order_by("created_at")
    )

    if len(active_sessions) >= limit:
        # Revoke oldest
        oldest = active_sessions[0]
        oldest.revoked_at = timezone.now()
        oldest.save(update_fields=["revoked_at"])


def _parse_device(request: object) -> dict[str, str]:
    ua = getattr(getattr(request, "META", {}), "get", lambda k, d: d)("HTTP_USER_AGENT", "")
    return {"user_agent": ua[:500]}


def _get_ip(request: object) -> str | None:
    x_forwarded = getattr(getattr(request, "META", {}), "get", lambda k, d: d)("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return getattr(getattr(request, "META", {}), "get", lambda k, d: d)("REMOTE_ADDR", None)
