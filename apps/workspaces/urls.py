from django.urls import path
from apps.workspaces import views

urlpatterns = [
    path("workspaces/", views.WorkspaceCreateView.as_view(), name="workspace-create"),
    path("workspace/", views.WorkspaceDetailView.as_view(), name="workspace-detail"),
    path("workspace/branding/", views.WorkspaceBrandingView.as_view(), name="workspace-branding"),
    path("workspaces/subdomain-available/", views.SubdomainCheckView.as_view(), name="subdomain-check"),
    path("team/invitations/", views.TeamInvitationView.as_view(), name="team-invitations"),
    path("team/invitations/<str:token>/accept/", views.TeamInvitationAcceptView.as_view(), name="team-invite-accept"),
    path("team/<int:pk>/permissions/", views.TeamMemberPermissionsView.as_view(), name="team-permissions"),
    path("invite-links/", views.InviteLinkView.as_view(), name="invite-links"),
    path("invite-links/<str:token>/resolve/", views.InviteLinkResolveView.as_view(), name="invite-link-resolve"),
]
