from django.urls import path
from apps.groups import views

urlpatterns = [
    path("groups/", views.GroupListCreateView.as_view(), name="group-list"),
    path("groups/<int:pk>/", views.GroupDetailView.as_view(), name="group-detail"),
    path("groups/<int:group_id>/members/", views.GroupMemberView.as_view(), name="group-members"),
    path("groups/<int:group_id>/sessions/", views.SessionListCreateView.as_view(), name="session-list"),
    path("sessions/<int:session_id>/attendance/", views.AttendanceBulkView.as_view(), name="attendance-bulk"),
]
