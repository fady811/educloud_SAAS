from django.urls import path
from apps.reports import views

urlpatterns = [
    path("reports/attendance/", views.AttendanceReportView.as_view(), name="report-attendance"),
    path("reports/payments/", views.PaymentReportView.as_view(), name="report-payments"),
    path("reports/enrollment/", views.EnrollmentReportView.as_view(), name="report-enrollment"),
]
