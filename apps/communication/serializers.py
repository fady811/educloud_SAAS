from rest_framework import serializers
from apps.communication.models import Announcement, Conversation, Message

class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "author", "scope", "target_id", "title", "body_html", "is_pinned", "published_at"]

class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "participant_a", "participant_b", "last_message_at"]

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "body", "parent_message", "attachment_file_id", "read_at", "created_at"]
