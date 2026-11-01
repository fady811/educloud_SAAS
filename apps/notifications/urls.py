from rest_framework.routers import DefaultRouter
from apps.notifications.views import NotificationViewSet, NotificationPreferenceViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")
router.register("notifications/preferences", NotificationPreferenceViewSet, basename="notification-preference")
urlpatterns = router.urls
