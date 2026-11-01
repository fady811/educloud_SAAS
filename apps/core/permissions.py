"""DRF permission classes (§15.3)."""
from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView


class IsWorkspaceMember(IsAuthenticated):
    """User must be authenticated and a member of the resolved workspace."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        workspace_id = getattr(request, "workspace_id", None)
        if not workspace_id:
            return False
        return _has_membership(request.user, workspace_id)


class IsWorkspaceOwner(IsWorkspaceMember):
    """Teacher-only: the user must be the workspace owner (§5.17, REQ-ROLE-03)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        workspace_id = getattr(request, "workspace_id", None)
        return _is_owner(request.user, workspace_id)


class IsSuperAdmin(IsAuthenticated):
    """Platform-level Super Admin (§2.3 ACT-01)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        return bool(getattr(request.user, "is_super_admin", False))


class HasPermissionKey(IsWorkspaceMember):
    """
    Team member permission gate (REQ-ROLE-02).
    Subclass and set `permission_key` or pass it via `get_permission_key()`.
    """

    permission_key: str = ""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        key = self.permission_key or getattr(view, "required_permission_key", "")
        if not key:
            return False
        workspace_id = getattr(request, "workspace_id", None)
        return _check_permission_key(request.user, workspace_id, key)


class GracePeriodGate(BasePermission):
    """
    Blocks student write operations in GRACE_PERIOD (REQ-WS-08a).
    Apply to write views for student-initiated actions.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.workspaces.services.lifecycle import grace_capability
        workspace_id = getattr(request, "workspace_id", None)
        if not workspace_id or not request.user.is_authenticated:
            return True  # let other permission classes handle it
        action = getattr(view, "grace_action", None)
        if not action:
            return True
        return grace_capability(workspace_id, action, request.user)


class IsParentOfStudent(IsAuthenticated):
    """Parent portal: the parent must be linked to the student in the URL (REQ-PARENT-03)."""

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        from apps.parents.models import ParentStudentLink
        student_id = getattr(obj, "id", None) or getattr(obj, "student_id", None)
        workspace_id = getattr(request, "workspace_id", None)
        if not student_id or not workspace_id:
            return False
        return ParentStudentLink.objects.filter(
            workspace_id=workspace_id,
            parent_user=request.user,
            student_user_id=student_id,
        ).exists()


# ---------------------------------------------------------------------------
# Helpers (lazy imports to avoid circular deps)
# ---------------------------------------------------------------------------

def _has_membership(user: object, workspace_id: int) -> bool:
    try:
        from apps.workspaces.models import WorkspaceMembership
        return WorkspaceMembership.objects.filter(
            user=user, workspace_id=workspace_id
        ).exists()
    except Exception:  # noqa: BLE001
        return False


def _is_owner(user: object, workspace_id: int | None) -> bool:
    if not workspace_id:
        return False
    try:
        from apps.workspaces.models import WorkspaceMembership
        return WorkspaceMembership.objects.filter(
            user=user, workspace_id=workspace_id, is_owner=True
        ).exists()
    except Exception:  # noqa: BLE001
        return False


def _check_permission_key(user: object, workspace_id: int | None, key: str) -> bool:
    if not workspace_id:
        return False
    try:
        from apps.accounts.services.permissions import has_permission
        return has_permission(user, workspace_id, key)
    except Exception:  # noqa: BLE001
        return False
