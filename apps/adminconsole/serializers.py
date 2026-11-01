from rest_framework import serializers
from apps.adminconsole.models import ContentReport

class ContentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentReport
        fields = ["id", "workspace_id", "reporter_id", "content_type", "content_id",
                  "reason", "status", "reviewed_at", "resolution"]
