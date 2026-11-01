"""
Accounts models (§5.1.2, §12.4.3).
User is global — no workspace_id. WorkspaceMembership is in workspaces app.
"""
from __future__ import annotations

import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.enums import Role
from apps.core.models import TimeStampedModel
from apps.core.validators import normalize_phone, validate_phone


class UserManager(BaseUserManager):
    def create_user(
        self,
        email: str | None = None,
        phone: str | None = None,
        password: str | None = None,
        **extra: object,
    ) -> "User":
        if not email and not phone:
            raise ValueError("Either email or phone is required.")
        if email:
            email = self.normalize_email(email)
        if phone:
            phone = normalize_phone(phone)
        user = self.model(email=email, phone=phone, **extra)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra: object) -> "User":
        extra.setdefault("is_super_admin", True)
        return self.create_user(email=email, password=password, **extra)


class User(AbstractBaseUser, TimeStampedModel):
    """
    Global identity (§5.1.2, §5.1.3).
    email OR phone — exactly one is required as the login identifier (C-04, DR-034).
    Phone-only CSV-imported students have no email.
    """

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        validators=[validate_phone],
    )

    # Names — Arabic-capable UTF-8 (CON-01)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")

    # Platform-level admin flag (INV-03 — SUPER_ADMIN never holds a WorkspaceMembership)
    is_super_admin = models.BooleanField(default=False)

    # Verification
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    # Soft-delete
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Django compat
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # unused but required by Django admin

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        app_label = "accounts"
        db_table = "users"
        indexes = [
            models.Index(fields=["email"], name="users_email_idx"),
            models.Index(fields=["phone"], name="users_phone_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email__isnull=False) | models.Q(phone__isnull=False),
                name="users_email_or_phone_required",
            ),
        ]

    @property
    def is_verified(self) -> bool:
        return (self.email_verified_at is not None) or (self.phone_verified_at is not None)

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email or self.phone or ""

    def __str__(self) -> str:
        return self.display_name


class UserSession(TimeStampedModel):
    """Tracks active sessions per user for device management (REQ-SEC-05/06/07)."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="sessions")
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, null=True, blank=True,
    )
    session_key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    device_info = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "accounts"
        db_table = "user_sessions"
        indexes = [
            models.Index(fields=["user", "revoked_at"], name="user_sessions_user_active_idx"),
        ]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class VerificationToken(TimeStampedModel):
    """Single-use email/phone verification tokens (REQ-SEC-01)."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    purpose = models.CharField(max_length=30)  # email_verification | phone_activation
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"
        db_table = "verification_tokens"


class PasswordResetToken(TimeStampedModel):
    """Single-use password reset tokens (REQ-SEC-03)."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"
        db_table = "password_reset_tokens"


class TeamMemberPermission(TimeStampedModel):
    """
    Granular per-member permission rows (REQ-ROLE-02, §5.13.2).
    Absence of a row for a key = denied (fail-closed).
    """

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE)
    permission_key = models.CharField(max_length=80)  # PermissionKey enum value

    class Meta:
        app_label = "accounts"
        db_table = "team_member_permissions"
        unique_together = [("user", "workspace", "permission_key")]
        indexes = [
            models.Index(fields=["user", "workspace"], name="tmp_user_ws_idx"),
        ]


class TeamInvitation(TimeStampedModel):
    """Workspace team invitations (REQ-TEAM-01)."""

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(max_length=20, default=Role.TEAM_MEMBER)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="sent_invitations"
    )

    class Meta:
        app_label = "accounts"
        db_table = "team_invitations"


class WorkspaceInviteLink(TimeStampedModel):
    """Shareable self-registration invite links (REQ-CONTENT-08a)."""

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    subject = models.ForeignKey("content.Subject", on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey("groups.Group", on_delete=models.SET_NULL, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)

    class Meta:
        app_label = "accounts"
        db_table = "workspace_invite_links"


class StudentImportJob(TimeStampedModel):
    """Tracks a CSV import operation (REQ-CONTENT-08a)."""

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    total_rows = models.IntegerField(default=0)
    created_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default="PROCESSING")
    file_ref = models.CharField(max_length=500, blank=True)

    class Meta:
        app_label = "accounts"
        db_table = "student_import_jobs"


class StudentImportRow(TimeStampedModel):
    """Per-row result of a CSV import (REQ-CONTENT-08a)."""

    job = models.ForeignKey("accounts.StudentImportJob", on_delete=models.CASCADE, related_name="rows")
    row_number = models.IntegerField()
    raw_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20)  # CREATED | SKIPPED
    error_code = models.CharField(max_length=80, blank=True)
    error_detail = models.CharField(max_length=500, blank=True)
    created_user = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        app_label = "accounts"
        db_table = "student_import_rows"
        unique_together = [("job", "row_number")]
