from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.payments.views import StudentPaymentViewSet, WorkspacePaymentMethodViewSet, PaymentDueView

router = DefaultRouter()
router.register("student-payments", StudentPaymentViewSet, basename="student-payment")
router.register("payment-methods", WorkspacePaymentMethodViewSet, basename="payment-method")
urlpatterns = router.urls + [
    path("due/", PaymentDueView.as_view(), name="payments-due"),
]
