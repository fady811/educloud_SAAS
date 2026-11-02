"""Account serializers."""
from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import User, UserSession, TeamMemberPermission, StudentImportJob
from apps.accounts.enums import PermissionKey
from apps.core.validators import validate_phone, normalize_phone


class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")

    def validate(self, data: dict) -> dict:
        if not data.get("email") and not data.get("phone"):
            raise serializers.ValidationError("Either email or phone is required.")
        if data.get("phone"):
            data["phone"] = normalize_phone(data["phone"])
            validate_phone(data["phone"])
        return data


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()  # email or phone
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "phone", "first_name", "last_name", "is_verified", "created_at"]
        read_only_fields = ["id", "is_verified", "created_at"]


class UserSessionSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = ["id", "device_info", "ip_address", "created_at", "last_active_at", "is_current"]

    def get_is_current(self, obj: UserSession) -> bool:
        request = self.context.get("request")
        if not request:
            return False
        import hashlib
        session_key = getattr(request.session, "session_key", None)
        if not session_key:
            return False
        return obj.session_key_hash == hashlib.sha256(session_key.encode()).hexdigest()


class PermissionKeySerializer(serializers.Serializer):
    keys = serializers.MultipleChoiceField(choices=PermissionKey.values)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8)


class WorkspaceMembershipStudentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.id")
    email = serializers.EmailField(source="user.email", allow_null=True)
    phone = serializers.CharField(source="user.phone", allow_null=True)
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    is_active = serializers.BooleanField()
    joined_at = serializers.DateTimeField(source="created_at")


class StudentImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentImportJob
        fields = ["id", "status", "total_rows", "created_count", "skipped_count", "created_at", "updated_at"]
        read_only_fields = fields
