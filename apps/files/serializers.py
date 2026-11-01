"""File serializers."""
from __future__ import annotations

from rest_framework import serializers


class StoredFileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    key = serializers.CharField()
    original_name = serializers.CharField()
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    category = serializers.CharField()
    scan_status = serializers.CharField()
    is_public = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str | None:
        from apps.files.services.storage import get_presigned_url
        try:
            return get_presigned_url(obj.key)
        except Exception:
            return None


class UploadRequestSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=20)
    size_bytes = serializers.IntegerField(min_value=1)
