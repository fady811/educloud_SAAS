"""Communication views — announcements, DM conversations, messages."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet

from apps.core.permissions import WorkspacePermission, ALL_MEMBERS, NON_PARENT
from apps.accounts.enums import PermissionKey
from apps.communication.models import Announcement, Conversation, Message
from apps.communication.serializers import AnnouncementSerializer, ConversationSerializer, MessageSerializer


class AnnouncementViewSet(ModelViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = AnnouncementSerializer
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.COMM_ANNOUNCEMENTS},
        "PUT": {"required_permission_key": PermissionKey.COMM_ANNOUNCEMENTS},
        "PATCH": {"required_permission_key": PermissionKey.COMM_ANNOUNCEMENTS},
        "DELETE": {"required_permission_key": PermissionKey.COMM_ANNOUNCEMENTS},
    }

    def get_queryset(self):
        return Announcement.objects.filter(
            workspace_id=self.request.workspace_id,
            published_at__isnull=False,
        ).order_by("-published_at")

    def perform_create(self, serializer):
        serializer.save(
            workspace_id=self.request.workspace_id,
            author=self.request.user,
        )


class ConversationViewSet(ListModelMixin, RetrieveModelMixin, CreateModelMixin, GenericViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = ConversationSerializer
    # REQ-PARENT-05: PARENT may not initiate DMs
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"allowed_roles": NON_PARENT},
    }

    def get_queryset(self):
        u = self.request.user.id
        return Conversation.objects.filter(workspace_id=self.request.workspace_id).filter(
            Q(participant_a_id=u) | Q(participant_b_id=u)
        ).order_by("-last_message_at")

    def create(self, request, *args, **kwargs):
        from apps.communication.services.messaging import get_or_create_conversation
        from apps.core.errors import PermissionDeniedError
        from apps.core.enums import Role
        from apps.workspaces.models import WorkspaceMembership
        from apps.accounts.services.permissions import has_permission

        other_user_id = request.data.get("other_user_id")
        if not other_user_id:
            from apps.core.errors import ValidationFailed
            raise ValidationFailed("other_user_id is required.")

        # TEAM_MEMBER needs COMM_DMS key; TEACHER (owner) bypasses; STUDENT allowed freely
        try:
            m = WorkspaceMembership.objects.get(user=request.user, workspace_id=request.workspace_id)
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if m.role == Role.TEAM_MEMBER and not m.is_owner:
            if not has_permission(request.user, request.workspace_id, PermissionKey.COMM_DMS):
                raise PermissionDeniedError("You do not have permission to send direct messages.")

        conv = get_or_create_conversation(
            workspace_id=request.workspace_id,
            initiator_id=request.user.id,
            other_user_id=int(other_user_id),
        )
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        conv = self.get_object()
        from apps.communication.services.messaging import assert_participant
        assert_participant(conv, request.user.id)
        return Response(ConversationSerializer(conv).data)


class MessageViewSet(ListModelMixin, CreateModelMixin, GenericViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = MessageSerializer
    # REQ-PARENT-05: PARENT may not send messages
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"allowed_roles": NON_PARENT},
        "DELETE": {"allowed_roles": ALL_MEMBERS},
    }

    def get_queryset(self):
        from apps.communication.services.messaging import assert_participant
        conv_id = self.kwargs.get("conversation_pk") or self.request.query_params.get("conversation")
        if not conv_id:
            from apps.core.errors import ValidationFailed
            raise ValidationFailed("conversation parameter is required.")
        try:
            conv = Conversation.objects.get(id=conv_id, workspace_id=self.request.workspace_id)
        except Conversation.DoesNotExist:
            from apps.core.errors import NotFound
            raise NotFound("Conversation not found.")
        assert_participant(conv, self.request.user.id)
        return Message.objects.filter(
            conversation_id=conv_id,
            workspace_id=self.request.workspace_id,
            deleted_at__isnull=True,
        ).order_by("created_at")

    def create(self, request, *args, **kwargs):
        from apps.communication.services.messaging import send_message
        from apps.core.errors import PermissionDeniedError
        from apps.core.enums import Role
        from apps.workspaces.models import WorkspaceMembership
        from apps.accounts.services.permissions import has_permission

        conv_id = kwargs.get("conversation_pk") or request.data.get("conversation")
        if not conv_id:
            from apps.core.errors import ValidationFailed
            raise ValidationFailed("conversation is required.")

        # TEAM_MEMBER needs COMM_DMS key
        try:
            m = WorkspaceMembership.objects.get(user=request.user, workspace_id=request.workspace_id)
        except WorkspaceMembership.DoesNotExist:
            raise PermissionDeniedError("Not a workspace member.")

        if m.role == Role.TEAM_MEMBER and not m.is_owner:
            if not has_permission(request.user, request.workspace_id, PermissionKey.COMM_DMS):
                raise PermissionDeniedError("You do not have permission to send direct messages.")

        msg = send_message(
            workspace_id=request.workspace_id,
            conversation_id=int(conv_id),
            sender_id=request.user.id,
            body=request.data.get("body", ""),
            parent_message_id=request.data.get("parent_message"),
            attachment_file_id=request.data.get("attachment_file_id"),
        )
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        import hashlib
        import json
        qs = self.get_queryset()
        data = self.get_serializer(qs, many=True).data
        new_etag = hashlib.md5(json.dumps([d["id"] for d in data]).encode()).hexdigest()
        etag = request.META.get("HTTP_IF_NONE_MATCH", "")
        if etag and etag == new_etag:
            return Response(status=304)
        response = Response(data)
        response["ETag"] = new_etag
        return response

    @action(detail=False, methods=["post"], url_path="read")
    def mark_read(self, request, *args, **kwargs):
        from apps.communication.services.messaging import mark_read
        conv_id = kwargs.get("conversation_pk") or request.data.get("conversation")
        if not conv_id:
            from apps.core.errors import ValidationFailed
            raise ValidationFailed("conversation is required.")
        count = mark_read(
            workspace_id=request.workspace_id,
            conversation_id=int(conv_id),
            reader_id=request.user.id,
            up_to_message_id=request.data.get("up_to_message_id"),
        )
        return Response({"marked_read": count})

    @action(detail=True, methods=["delete"])
    def destroy_message(self, request, *args, **kwargs):
        from apps.communication.services.messaging import delete_message
        delete_message(
            workspace_id=request.workspace_id,
            message_id=kwargs["pk"],
            requester_id=request.user.id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
