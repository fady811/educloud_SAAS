"""Communication models: Announcement, Conversation, Message."""
from __future__ import annotations

from django.db import models

from apps.core.enums import AnnouncementScope
from apps.core.models import TenantModel
from apps.core.validators import sanitize_html


class Announcement(TenantModel):
    author = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="announcements")
    scope = models.CharField(max_length=20, choices=AnnouncementScope.choices, default=AnnouncementScope.WORKSPACE)
    target_id = models.BigIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    body_html = models.TextField()
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        app_label = "communication"
        db_table = "communication_announcements"
        indexes = [
            models.Index(fields=["workspace", "scope", "published_at"], name="ann_scope_pub_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.body_html:
            self.body_html = sanitize_html(self.body_html)
        super().save(*args, **kwargs)


class Conversation(TenantModel):
    """DM thread between two workspace members (REQ-COM-03)."""

    participant_a = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="conversations_as_a")
    participant_b = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="conversations_as_b")
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    etag = models.CharField(max_length=40, blank=True)

    class Meta:
        app_label = "communication"
        db_table = "communication_conversations"
        unique_together = [("workspace", "participant_a", "participant_b")]
        indexes = [
            models.Index(fields=["workspace", "participant_a", "last_message_at"], name="conv_a_idx"),
            models.Index(fields=["workspace", "participant_b", "last_message_at"], name="conv_b_idx"),
        ]


class Message(TenantModel):
    conversation = models.ForeignKey("communication.Conversation", on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    # Thread-ready (REQ-COM-05)
    parent_message = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    attachment_file_id = models.BigIntegerField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "communication"
        db_table = "communication_messages"
        indexes = [
            models.Index(fields=["conversation", "-created_at"], name="msg_conv_idx"),
        ]
