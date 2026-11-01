"""Workspace serializers."""
from __future__ import annotations

from rest_framework import serializers

from apps.core.validators import validate_subdomain, validate_hex_color


class WorkspaceCreateSerializer(serializers.Serializer):
    subdomain = serializers.CharField(max_length=63)
    display_name = serializers.CharField(max_length=150, required=False, default="")

    def validate_subdomain(self, value: str) -> str:
        validate_subdomain(value)
        return value.lower()


class WorkspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subdomain = serializers.CharField(allow_null=True)
    display_name = serializers.SerializerMethodField()
    status = serializers.CharField()
    grace_period_days = serializers.IntegerField()
    settings_json = serializers.DictField()
    created_at = serializers.DateTimeField()

    def get_display_name(self, obj) -> str:
        return obj.settings_json.get("display_name", "")


class WorkspaceBrandingSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=150, required=False)
    logo_url = serializers.URLField(required=False, allow_blank=True)
    primary_color = serializers.CharField(required=False)
    secondary_color = serializers.CharField(required=False)

    def validate_primary_color(self, value: str) -> str:
        if value:
            validate_hex_color(value)
        return value

    def validate_secondary_color(self, value: str) -> str:
        if value:
            validate_hex_color(value)
        return value


class WorkspaceMembershipSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    workspace_id = serializers.IntegerField()
    role = serializers.CharField()
    is_owner = serializers.BooleanField()
    joined_at = serializers.DateTimeField(source="created_at", read_only=True)
