"""Workspace models (§12.4.3, §6.1)."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.enums import (
    CustomDomainStatus,
    DeactivationCause,
    LimitAction,
    LimitKey,
    Role,
    WorkspaceStatus,
)
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_subdomain, validate_hex_color


DEFAULT_BRANDING_SETTINGS = {
    "display_name": "",
    "logo_file_id": None,
    "theme": "DEFAULT",
    "primary_color": "#3B82F6",
    "landing_text": "",
    "description": "",
    "meta": {"title": "", "description": ""},
}

DEFAULT_LIMIT_POLICY = {
    LimitKey.MAX_STUDENTS: LimitAction.BLOCK_NEW,
    LimitKey.STORAGE_GB: LimitAction.BLOCK_NEW,
    LimitKey.MAX_SUBJECTS_COURSES: LimitAction.WARN,
    LimitKey.MAX_GROUPS: LimitAction.WARN,
    LimitKey.MAX_TEAM_MEMBERS: LimitAction.WARN,
}

THEME_CHOICES = [
    ("DEFAULT", "Default"),
    ("DARK", "Dark"),
    ("WARM", "Warm"),
    ("COOL", "Cool"),
]


class Workspace(TimeStampedModel):
    """The tenant root (§12.3 group C). NOT a TenantModel — no workspace_id on itself."""

    subdomain = models.CharField(
        max_length=32, unique=True, null=True, blank=True,
        validators=[validate_subdomain],
    )
    status = models.CharField(
        max_length=30, choices=WorkspaceStatus.choices, default=WorkspaceStatus.SETUP, db_index=True
    )
    deactivation_cause = models.CharField(
        max_length=20, choices=DeactivationCause.choices, null=True, blank=True
    )

    # Branding JSONB (§12.4.2, REQ-WS-05) — closed schema, unknown keys rejected (INV-20)
    settings_json = models.JSONField(default=dict, db_column="settings")

    # Grace period configurable per workspace (REQ-WS-08)
    grace_period_days = models.SmallIntegerField(default=7)

    # Soft delete (REQ-WS-10)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    purge_after = models.DateTimeField(null=True, blank=True, db_index=True)

    # Admin-configurable limit policy per workspace (REQ-SUB-17/18)
    limit_policy = models.JSONField(default=dict)

    # Admin-configurable retention (REQ-WS-10)
    retention_days = models.IntegerField(default=90)

    class Meta:
        app_label = "workspaces"
        db_table = "workspaces"

    @property
    def is_active(self) -> bool:
        return self.status == WorkspaceStatus.ACTIVE

    @property
    def is_in_grace(self) -> bool:
        return self.status == WorkspaceStatus.GRACE_PERIOD

    @property
    def student_access_allowed(self) -> bool:
        """Called by middleware to decide if students/parents can access (REQ-WS-03)."""
        return self.status in (WorkspaceStatus.ACTIVE, WorkspaceStatus.GRACE_PERIOD)

    def __str__(self) -> str:
        return f"{self.subdomain or 'no-subdomain'} ({self.status})"


class WorkspaceMembership(TimeStampedModel):
    """
    Links a User to a Workspace with a role (§5.1.2, C-01).
    INV-01: unique (user, workspace). INV-02: one is_owner per workspace.
    """

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="memberships")
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_owner = models.BooleanField(default=False)

    # Per-student billing anchor (Q-06, DR-031, INV-57)
    billing_anchor_date = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "workspaces"
        db_table = "workspace_memberships"
        unique_together = [("user", "workspace")]
        indexes = [
            models.Index(fields=["workspace", "role"], name="wm_workspace_role_idx"),
            models.Index(fields=["user"], name="wm_user_idx"),
        ]
        constraints = [
            # INV-02: exactly one owner per workspace
            models.UniqueConstraint(
                fields=["workspace"],
                condition=models.Q(is_owner=True),
                name="workspace_single_owner",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=[
                    "SUPER_ADMIN", "TEACHER", "TEAM_MEMBER", "STUDENT", "PARENT"
                ]),
                name="wm_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.workspace} ({self.role})"


class WorkspaceStatusHistory(TimeStampedModel):
    """Immutable record of every workspace status transition."""

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=30, choices=WorkspaceStatus.choices)
    to_status = models.CharField(max_length=30, choices=WorkspaceStatus.choices)
    triggered_by_id = models.BigIntegerField(null=True, blank=True)
    trigger_type = models.CharField(max_length=20, default="SYSTEM")
    reason = models.TextField(blank=True, default="")

    class Meta:
        app_label = "workspaces"
        db_table = "workspace_status_history"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "-created_at"], name="ws_history_ws_idx"),
        ]


class CustomDomain(TimeStampedModel):
    """Phase-2 custom domain shell (REQ-WS-14/16). Table created now, logic deferred."""

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, related_name="custom_domains")
    domain = models.CharField(max_length=253, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=CustomDomainStatus.choices, default=CustomDomainStatus.PENDING_DNS)
    verification_token = models.CharField(max_length=64, blank=True, default="")
    ssl_status = models.CharField(max_length=30, default="PENDING")

    class Meta:
        app_label = "workspaces"
        db_table = "custom_domains"
