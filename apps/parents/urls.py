from django.urls import path
from apps.parents import views

urlpatterns = [
    path("parent-links/", views.ParentLinkView.as_view(), name="parent-link"),
    path("parent-links/redeem/", views.RedeemLinkingCodeView.as_view(), name="parent-link-redeem"),
    path("my-students/", views.ParentStudentsView.as_view(), name="my-students"),
    path("students/<int:student_id>/linking-code/", views.StudentLinkingCodeView.as_view(), name="student-linking-code"),
]
