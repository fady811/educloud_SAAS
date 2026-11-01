from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from django.utils import timezone
from apps.core.permissions import IsWorkspaceMember
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user,
            workspace_id=self.request.workspace_id,
        ).order_by("-created_at")

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(read_at__isnull=True).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notif = self.get_object()
        if not notif.read_at:
            notif.read_at = timezone.now()
            notif.save(update_fields=["read_at"])
        return Response({"status": "ok"})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"status": "ok"})


class NotificationPreferenceViewSet(GenericViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = NotificationPreferenceSerializer

    def get_queryset(self):
        # Preferences are global per user (not workspace-scoped)
        return NotificationPreference.objects.filter(user=self.request.user)

    def list(self, request):
        qs = self.get_queryset()
        return Response(NotificationPreferenceSerializer(qs, many=True).data)

    def update(self, request, *args, **kwargs):
        data = request.data if isinstance(request.data, list) else [request.data]
        for item in data:
            NotificationPreference.objects.update_or_create(
                user=request.user,
                category=item["category"],
                defaults={"is_enabled": item.get("is_enabled", True)},
            )
        return Response({"status": "ok"})
