"""Groups serializers."""
from __future__ import annotations

from rest_framework import serializers


class GroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    subject_id = serializers.IntegerField(allow_null=True)
    teacher_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    max_students = serializers.IntegerField(allow_null=True)
    color = serializers.CharField()
    description = serializers.CharField()
    archived_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class GroupWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    subject_id = serializers.IntegerField(required=False, allow_null=True)
    teacher_id = serializers.IntegerField(required=False, allow_null=True)
    max_students = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    color = serializers.CharField(required=False, default="")
    description = serializers.CharField(required=False, default="")


class SessionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    group_id = serializers.IntegerField()
    title = serializers.CharField()
    scheduled_at = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField()
    notes = serializers.CharField()
    cancelled_at = serializers.DateTimeField(allow_null=True)


class AttendanceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    student_id = serializers.IntegerField()
    status = serializers.CharField()
    notes = serializers.CharField()


class AttendanceBulkSerializer(serializers.Serializer):
    records = serializers.ListField(child=serializers.DictField())
