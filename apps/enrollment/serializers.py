from __future__ import annotations
from rest_framework import serializers


class EnrollmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    student_id = serializers.IntegerField()
    enrollable_type = serializers.CharField()
    enrollable_id = serializers.IntegerField()
    status = serializers.CharField()
    enrolled_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    unenrolled_at = serializers.DateTimeField(allow_null=True)


class EnrollmentWriteSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    enrollable_type = serializers.CharField()
    enrollable_id = serializers.IntegerField()
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, default="")
