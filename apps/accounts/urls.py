from django.urls import path
from apps.accounts import views

urlpatterns = [
    # Student management
    path("students/", views.StudentListCreateView.as_view(), name="student-list"),
    path("students/<int:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("students/import/", views.StudentImportView.as_view(), name="student-import"),
    path("students/import/<int:pk>/", views.StudentImportDetailView.as_view(), name="student-import-detail"),

    # Auth
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/verify/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("auth/verify/resend/", views.ResendVerificationView.as_view(), name="verify-resend"),
    path("auth/password-reset/", views.PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("auth/password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("auth/sessions/", views.SessionListView.as_view(), name="session-list"),
    path("auth/sessions/<int:pk>/", views.SessionRevokeView.as_view(), name="session-revoke"),
    path("auth/sessions/revoke-others/", views.SessionRevokeView.as_view(), name="session-revoke-others"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/workspaces/", views.MeWorkspacesView.as_view(), name="me-workspaces"),
]
