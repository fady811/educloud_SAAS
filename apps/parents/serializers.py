from __future__ import annotations
from rest_framework import serializers


class ParentStudentLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parent_id = serializers.IntegerField()
    student_id = serializers.IntegerField()
    relationship = serializers.CharField()
    linked_at = serializers.DateTimeField()
    unlinked_at = serializers.DateTimeField(allow_null=True)
