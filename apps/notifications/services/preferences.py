from __future__ import annotations

def is_enabled(user_id: int, category: str) -> bool:
    """Absence of a preference row = enabled (REQ-NOTIF-04)."""
    from apps.notifications.models import NotificationPreference
    pref = NotificationPreference.objects.filter(user_id=user_id, category=category).first()
    if pref is None:
        return True
    return pref.is_enabled
