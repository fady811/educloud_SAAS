"""
has_permission() — the authoritative team member permission check (§5.13.2, REQ-ROLE-02).
Fail-closed: absence of a row = denied.
"""
from __future__ import annotations

from apps.core.enums import Role


def has_permission(user: object, workspace_id: int, key: str) -> bool:
    """
    Returns True if the user has the given permission key in this workspace.
    Owner (TEACHER) has all permissions implicitly.
    SUPER_ADMIN goes through admin_context() — this function is not called for admins.
    """
    from apps.workspaces.models import WorkspaceMembership
    from apps.accounts.models import TeamMemberPermission
    from apps.accounts.enums import PermissionKey

    # Key must be a valid PermissionKey
    if key not in PermissionKey.values:
        return False

    try:
        membership = WorkspaceMembership.objects.get(user=user, workspace_id=workspace_id)
    except WorkspaceMembership.DoesNotExist:
        return False

    # Owner always has all permissions (REQ-ROLE-03)
    if membership.is_owner:
        return True

    # Teachers and team members — check explicit grant
    if membership.role in (Role.TEACHER, Role.TEAM_MEMBER):
        return TeamMemberPermission.objects.filter(
            user=user, workspace_id=workspace_id, permission_key=key
        ).exists()

    # Students/Parents have no team permissions
    return False
