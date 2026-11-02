from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.billing.views import (
    AddonViewSet,
    PackageViewSet,
    SubscriptionViewSet,
    SubscriptionPaymentViewSet,
    UpgradeOptionsView,
    UpgradeQuoteView,
    UpgradeView,
)

router = DefaultRouter()
router.register("packages", PackageViewSet, basename="package")
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("subscription-payments", SubscriptionPaymentViewSet, basename="subscription-payment")
router.register("addons", AddonViewSet, basename="addon")

urlpatterns = router.urls + [
    path("upgrade-options/", UpgradeOptionsView.as_view(), name="billing-upgrade-options"),
    path("upgrade-quote/", UpgradeQuoteView.as_view(), name="billing-upgrade-quote"),
    path("upgrades/", UpgradeView.as_view(), name="billing-upgrades"),
]
