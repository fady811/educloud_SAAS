"""
Communication business logic: conversations, messages, read receipts.
REQ-COM-01..08 — workspace-scoped DMs, participant authorization, read receipts.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.errors import NotFound, PermissionDeniedError, ValidationFailed


def get_or_create_conversation(
    *,
    workspace_id: int,
    initiator_id: int,
    other_user_id: int,
) -> "Conversation":  # type: ignore[name-defined]
    """
    Return existing conversation between two workspace members, or create it.
    Canonical order: participant_a_id < participant_b_id to ensure unique_together
    constraint is never violated by reversed creation.
    Both users must be active workspace members.
    """
    from apps.communication.models import Conversation
    from apps.workspaces.models import WorkspaceMembership

    if initiator_id == other_user_id:
        raise ValidationFailed("Cannot start a conversation with yourself.")

    # Verify both parties are members of this workspace
    for uid in (initiator_id, other_user_id):
        if not WorkspaceMembership.objects.filter(
            workspace_id=workspace_id, user_id=uid
        ).exists():
            raise PermissionDeniedError(f"User {uid} is not a member of this workspace.")

    a_id, b_id = (initiator_id, other_user_id) if initiator_id < other_user_id else (other_user_id, initiator_id)

    conv, _ = Conversation.objects.get_or_create(
        workspace_id=workspace_id,
        participant_a_id=a_id,
        participant_b_id=b_id,
    )
    return conv


def assert_participant(conversation: "Conversation", user_id: int) -> None:  # type: ignore[name-defined]
    """Raise PermissionDeniedError if user is not a conversation participant."""
    if user_id not in (conversation.participant_a_id, conversation.participant_b_id):
        raise PermissionDeniedError("You are not a participant in this conversation.")


def send_message(
    *,
    workspace_id: int,
    conversation_id: int,
    sender_id: int,
    body: str,
    parent_message_id: int | None = None,
    attachment_file_id: int | None = None,
) -> "Message":  # type: ignore[name-defined]
    """
    Send a message in a conversation. Sender must be a participant.
    Updates conversation.last_message_at atomically.
    """
    from apps.communication.models import Conversation, Message

    if not body or not body.strip():
        raise ValidationFailed("Message body cannot be empty.")

    with transaction.atomic():
        try:
            conv = Conversation.objects.select_for_update().get(
                id=conversation_id, workspace_id=workspace_id
            )
        except Conversation.DoesNotExist:
            raise NotFound("Conversation not found.")

        assert_participant(conv, sender_id)

        # Validate parent message belongs to same conversation
        if parent_message_id is not None:
            if not Message.objects.filter(
                id=parent_message_id, conversation_id=conversation_id
            ).exists():
                raise ValidationFailed("Parent message not found in this conversation.")

        now = timezone.now()
        msg = Message.objects.create(
            workspace_id=workspace_id,
            conversation=conv,
            sender_id=sender_id,
            body=body.strip(),
            parent_message_id=parent_message_id,
            attachment_file_id=attachment_file_id,
        )

        conv.last_message_at = now
        conv.save(update_fields=["last_message_at", "updated_at"])

    return msg


def mark_read(
    *,
    workspace_id: int,
    conversation_id: int,
    reader_id: int,
    up_to_message_id: int | None = None,
) -> int:
    """
    Mark messages as read for the reader in a conversation.
    If up_to_message_id is given, marks only up to that message (inclusive).
    Returns count of messages marked.
    """
    from apps.communication.models import Conversation, Message

    try:
        conv = Conversation.objects.get(id=conversation_id, workspace_id=workspace_id)
    except Conversation.DoesNotExist:
        raise NotFound("Conversation not found.")

    assert_participant(conv, reader_id)

    qs = Message.objects.filter(
        conversation_id=conversation_id,
        read_at__isnull=True,
        deleted_at__isnull=True,
    ).exclude(sender_id=reader_id)  # Don't mark your own messages as read

    if up_to_message_id is not None:
        qs = qs.filter(id__lte=up_to_message_id)

    return qs.update(read_at=timezone.now())


def delete_message(
    *,
    workspace_id: int,
    message_id: int,
    requester_id: int,
) -> None:
    """Soft-delete a message. Only the sender may delete their own messages."""
    from apps.communication.models import Message

    try:
        msg = Message.objects.select_for_update().get(
            id=message_id,
            workspace_id=workspace_id,
            deleted_at__isnull=True,
        )
    except Message.DoesNotExist:
        raise NotFound("Message not found.")

    if msg.sender_id != requester_id:
        raise PermissionDeniedError("You can only delete your own messages.")

    msg.deleted_at = timezone.now()
    msg.save(update_fields=["deleted_at"])
