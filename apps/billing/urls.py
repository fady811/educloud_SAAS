from rest_framework.routers import DefaultRouter
from apps.billing.views import PackageViewSet, SubscriptionViewSet, SubscriptionPaymentViewSet

router = DefaultRouter()
router.register("packages", PackageViewSet, basename="package")
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("subscription-payments", SubscriptionPaymentViewSet, basename="subscription-payment")
urlpatterns = router.urls
