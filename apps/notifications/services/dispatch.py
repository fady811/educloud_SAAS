from __future__ import annotations
from typing import Any
from apps.core.enums import NotificationCategory

_CHANNEL_REGISTRY: list[object] = []

def _get_channels() -> list[object]:
    if not _CHANNEL_REGISTRY:
        from apps.notifications.services.channels.in_app import InAppChannel
        _CHANNEL_REGISTRY.append(InAppChannel())
    return _CHANNEL_REGISTRY

def notify(
    *,
    user_id: int,
    workspace_id: int | None,
    category: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Single entry point for all notification creation (REQ-NOTIF-01)."""
    from apps.notifications.models import Notification, NotificationDelivery
    from apps.notifications.services.preferences import is_enabled

    if category not in NotificationCategory.values:
        raise ValueError(f"Unknown notification category: {category!r}")

    if not is_enabled(user_id, category):
        return

    notif = Notification.objects.create(
        user_id=user_id,
        workspace_id=workspace_id,
        category=category,
        payload=payload or {},
    )

    for channel in _get_channels():
        try:
            channel.deliver(notif)
            NotificationDelivery.objects.create(notification=notif, channel=channel.name, status="DELIVERED")
        except Exception as e:  # noqa: BLE001
            NotificationDelivery.objects.create(notification=notif, channel=channel.name, status="FAILED", error=str(e))
