from django.urls import path
from apps.enrollment import views

urlpatterns = [
    path("enrollments/", views.EnrollmentListCreateView.as_view(), name="enrollment-list"),
    path("enrollments/<int:pk>/", views.EnrollmentDetailView.as_view(), name="enrollment-detail"),
]
