from django.urls import path
from apps.accounts import views

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/sessions/", views.SessionListView.as_view(), name="session-list"),
    path("auth/sessions/<int:pk>/", views.SessionRevokeView.as_view(), name="session-revoke"),
    path("auth/sessions/revoke-others/", views.SessionRevokeView.as_view(), name="session-revoke-others"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/workspaces/", views.MeWorkspacesView.as_view(), name="me-workspaces"),
]
