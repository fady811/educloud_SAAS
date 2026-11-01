from rest_framework.routers import DefaultRouter
from apps.communication.views import AnnouncementViewSet, ConversationViewSet, MessageViewSet

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("messages", MessageViewSet, basename="message")
urlpatterns = router.urls
