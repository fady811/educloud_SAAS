from django.urls import path
from apps.adminconsole import views

urlpatterns = [
    path("workspaces/", views.WorkspaceListView.as_view(), name="admin-workspace-list"),
    path("workspaces/<int:pk>/status/", views.WorkspaceStatusView.as_view(), name="admin-workspace-status"),
    path("users/", views.UserListView.as_view(), name="admin-user-list"),
    path("packages/", views.PackageListCreateView.as_view(), name="admin-packages"),
]
