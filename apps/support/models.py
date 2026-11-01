"""Support ticket models (§12.4.12)."""
from __future__ import annotations

from django.db import models

from apps.core.enums import TicketStatus, TicketCategory
from apps.core.models import TenantModel


class SupportTicket(TenantModel):
    submitted_by_id = models.BigIntegerField()
    category = models.CharField(max_length=40, choices=TicketCategory.choices)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN)
    assigned_to_id = models.BigIntegerField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "support"
        db_table = "support_tickets"
        indexes = [
            models.Index(fields=["workspace", "status"], name="ticket_ws_status_idx"),
        ]


class TicketMessage(TenantModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author_id = models.BigIntegerField()
    body = models.TextField()
    is_internal = models.BooleanField(default=False)

    class Meta:
        app_label = "support"
        db_table = "ticket_messages"
