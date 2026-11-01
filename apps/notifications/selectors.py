from apps.notifications.models import Notification

def get_unread_notifications(user_id: int, workspace_id: int | None):
    return Notification.objects.filter(user_id=user_id, workspace_id=workspace_id, read_at__isnull=True).order_by("-created_at")
