from __future__ import annotations
from rest_framework import serializers


class TicketSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    category = serializers.CharField()
    subject = serializers.CharField()
    body = serializers.CharField()
    status = serializers.CharField()
    submitted_by_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class TicketWriteSerializer(serializers.Serializer):
    category = serializers.CharField()
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()


class TicketMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    author_id = serializers.IntegerField()
    body = serializers.CharField()
    is_internal = serializers.BooleanField()
    created_at = serializers.DateTimeField()
