from __future__ import annotations
from django.db import models
from apps.core.models import TimeStampedModel
from apps.core.enums import NotificationCategory


class Notification(TimeStampedModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, null=True, blank=True)
    category = models.CharField(max_length=50, choices=NotificationCategory.choices, db_index=True)
    payload = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "notifications"
        db_table = "notifications"
        indexes = [
            models.Index(fields=["user", "workspace", "read_at", "-created_at"], name="notif_user_ws_idx"),
        ]


class NotificationPreference(TimeStampedModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notification_preferences")
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, null=True, blank=True)
    category = models.CharField(max_length=50, choices=NotificationCategory.choices)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        app_label = "notifications"
        db_table = "notification_preferences"
        unique_together = [("user", "category")]


class NotificationDelivery(TimeStampedModel):
    notification = models.ForeignKey("notifications.Notification", on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default="PENDING")
    error = models.TextField(blank=True, default="")

    class Meta:
        app_label = "notifications"
        db_table = "notification_deliveries"
