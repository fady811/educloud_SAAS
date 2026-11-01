from django.urls import path
from apps.parents import views

urlpatterns = [
    path("parent-links/", views.ParentLinkView.as_view(), name="parent-link"),
    path("my-students/", views.ParentStudentsView.as_view(), name="my-students"),
]
