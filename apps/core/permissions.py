"""DRF permission classes (§15.3)."""
from __future__ import annotations

import logging

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role-set constants for use in permission_map declarations
# ---------------------------------------------------------------------------

ALL_MEMBERS = frozenset(["TEACHER", "TEAM_MEMBER", "STUDENT", "PARENT"])
STAFF_ONLY = frozenset(["TEACHER", "TEAM_MEMBER"])
STUDENT_ONLY = frozenset(["STUDENT"])
PARENT_ONLY = frozenset(["PARENT"])
NON_PARENT = frozenset(["TEACHER", "TEAM_MEMBER", "STUDENT"])


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


class WorkspacePermission(IsWorkspaceMember):
    """
    Declarative role/key permission gate (REQ-ROLE-02, §15.3).

    Every view using this class MUST declare ``permission_map``:

        permission_map = {
            "GET":    {"allowed_roles": ALL_MEMBERS},
            "POST":   {"required_permission_key": PermissionKey.CONTENT_CREATE},
            "PATCH":  {"required_permission_key": PermissionKey.CONTENT_EDIT},
            "DELETE": {"owner_only": True},
        }

    Rule dict keys:
      allowed_roles           frozenset[str]  — roles permitted (Role enum values).
      required_permission_key str             — PermissionKey; OWNER bypasses implicitly.
      owner_only              bool            — only the workspace owner (is_owner=True).
      allow_roles_without_key frozenset[str]  — roles that bypass required_permission_key.
                                                Roles NOT in this set still need the key.
                                                Used when some roles (e.g. STUDENT) need
                                                access to their own data without a key grant.

    If a method is absent from the map the request is denied.
    If the view declares no permission_map at all, every method is denied and an
    error is logged — views must be explicit.

    SUPER_ADMIN bypasses all workspace checks.
    Workspace OWNER (is_owner=True) bypasses required_permission_key.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False

        user = request.user
        workspace_id = getattr(request, "workspace_id", None)

        # SUPER_ADMIN bypasses all workspace checks
        if getattr(user, "is_super_admin", False):
            return True

        # Views must declare an explicit permission_map — fail closed with log
        permission_map = getattr(view, "permission_map", None)
        if permission_map is None:
            _log.error(
                "WorkspacePermission: view %s declares no permission_map — denying request",
                view.__class__.__name__,
            )
            return False

        method = request.method.upper()
        rule = permission_map.get(method)
        if rule is None:
            return False

        # Resolve membership (already confirmed present by IsWorkspaceMember)
        try:
            from apps.workspaces.models import WorkspaceMembership
            membership = WorkspaceMembership.objects.get(user=user, workspace_id=workspace_id)
        except Exception:  # noqa: BLE001
            return False

        # owner_only — workspace owner only
        if rule.get("owner_only"):
            return bool(membership.is_owner)

        # allowed_roles check
        allowed_roles = rule.get("allowed_roles")
        if allowed_roles is not None and membership.role not in allowed_roles:
            return False

        # required_permission_key — owner bypasses; allow_roles_without_key bypasses for listed roles
        required_key = rule.get("required_permission_key")
        if required_key:
            if membership.is_owner:
                return True
            allow_without_key = rule.get("allow_roles_without_key", frozenset())
            if membership.role in allow_without_key:
                return True
            return _check_permission_key(user, workspace_id, required_key)

        return True


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
