"""Login/logout flows."""
from __future__ import annotations

from django.contrib.auth import authenticate

from apps.accounts.services.login_throttle import check_login_allowed, record_failure, clear_counter
from apps.accounts.services.sessions import create_session
from apps.core.errors import ValidationFailed


def login(*, identifier: str, password: str, ip: str, request) -> dict:
    check_login_allowed(identifier=identifier, ip=ip)
    user = authenticate(username=identifier, password=password)
    if not user:
        record_failure(identifier, ip)
        raise ValidationFailed("Invalid credentials.", code="INVALID_CREDENTIALS")
    clear_counter(identifier)
    role = _resolve_role(user, request)
    session_key = create_session(user=user, request=request, role=role)
    return {"session_key": session_key, "user_id": user.id}


def _resolve_role(user, request) -> str:
    from apps.core.enums import Role
    from apps.workspaces.models import WorkspaceMembership

    workspace_id = getattr(request, "workspace_id", None)
    if user.is_super_admin:
        return "SUPER_ADMIN"
    if workspace_id:
        try:
            m = WorkspaceMembership.objects.get(user=user, workspace_id=workspace_id)
            return m.role
        except WorkspaceMembership.DoesNotExist:
            pass
    return Role.STUDENT
