"""Content serializers."""
from __future__ import annotations

from rest_framework import serializers


class SubjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    grade_level = serializers.CharField()
    color = serializers.CharField()
    archived_at = serializers.DateTimeField(allow_null=True)


class CourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    visibility = serializers.CharField()
    pricing_type = serializers.CharField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True, coerce_to_string=True)
    subject_id = serializers.IntegerField(allow_null=True)
    archived_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class CourseWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, default="")
    visibility = serializers.ChoiceField(choices=["DRAFT", "PUBLISHED", "ARCHIVED"], required=False, default="DRAFT")
    pricing_type = serializers.CharField(required=False, default="FREE")
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    subject_id = serializers.IntegerField(required=False, allow_null=True)


class LessonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    parent_type = serializers.CharField()
    parent_id = serializers.IntegerField()
    order = serializers.IntegerField()
    is_free_preview = serializers.BooleanField()
    archived_at = serializers.DateTimeField(allow_null=True)


class LessonContentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    content_type = serializers.CharField()
    body = serializers.CharField()
    file_id = serializers.IntegerField(allow_null=True)
    order = serializers.IntegerField()
    duration_seconds = serializers.IntegerField(allow_null=True)
