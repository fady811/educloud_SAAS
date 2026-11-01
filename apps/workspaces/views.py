"""Workspace views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsWorkspaceOwner, IsWorkspaceMember, IsSuperAdmin
from apps.workspaces.serializers import (
    WorkspaceCreateSerializer,
    WorkspaceBrandingSerializer,
    WorkspaceSerializer,
)


class WorkspaceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from apps.workspaces.services.provisioning import create_workspace
        ser = WorkspaceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = create_workspace(
            owner_id=request.user.id,
            subdomain=ser.validated_data["subdomain"],
            display_name=ser.validated_data.get("display_name", ""),
        )
        return Response(WorkspaceSerializer(ws).data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request: Request) -> Response:
        from apps.workspaces.models import Workspace
        ws = Workspace.objects.get(id=request.workspace_id)
        return Response(WorkspaceSerializer(ws).data)


class WorkspaceBrandingView(APIView):
    permission_classes = [IsWorkspaceOwner]

    def get(self, request: Request) -> Response:
        from apps.workspaces.models import Workspace
        ws = Workspace.objects.get(id=request.workspace_id)
        return Response(ws.settings_json)

    def patch(self, request: Request) -> Response:
        from apps.workspaces.services.branding import update_branding
        ws = update_branding(request.workspace_id, request.data, actor_id=request.user.id)
        return Response(ws.settings_json)


class SubdomainCheckView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "subdomain_check"

    def get(self, request: Request) -> Response:
        from apps.workspaces.services.subdomain import check_available
        slug = request.query_params.get("slug", "")
        return Response(check_available(slug))


class TeamInvitationView(APIView):
    permission_classes = [IsWorkspaceOwner]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.team import invite_team_member
        invitation = invite_team_member(
            workspace_id=request.workspace_id,
            invited_by_id=request.user.id,
            email=request.data.get("email", ""),
        )
        return Response({"id": invitation.id, "email": invitation.email}, status=status.HTTP_201_CREATED)


class TeamInvitationAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, token: str) -> Response:
        from apps.accounts.services.team import accept_invitation
        membership = accept_invitation(token=token, user=request.user)
        return Response({"workspace_id": membership.workspace_id, "role": membership.role})


class TeamMemberPermissionsView(APIView):
    permission_classes = [IsWorkspaceOwner]

    def get(self, request: Request, pk: int) -> Response:
        from apps.accounts.models import TeamMemberPermission
        keys = list(
            TeamMemberPermission.objects.filter(
                user_id=pk, workspace_id=request.workspace_id
            ).values_list("permission_key", flat=True)
        )
        return Response({"keys": keys})

    def put(self, request: Request, pk: int) -> Response:
        from apps.accounts.models import TeamMemberPermission
        from apps.accounts.enums import PermissionKey
        from apps.core import audit

        keys = request.data.get("keys", [])
        invalid = set(keys) - set(PermissionKey.values)
        if invalid:
            from apps.core.errors import ValidationFailed
            raise ValidationFailed(f"Unknown permission keys: {invalid}")

        TeamMemberPermission.objects.filter(user_id=pk, workspace_id=request.workspace_id).delete()
        for key in keys:
            TeamMemberPermission.objects.create(
                user_id=pk, workspace_id=request.workspace_id, permission_key=key
            )
        audit.record(
            actor_id=request.user.id,
            action="PERMISSION_CHANGED",
            target_type="User",
            target_id=pk,
            workspace_id=request.workspace_id,
            after={"keys": keys},
        )
        return Response({"keys": keys})


class InviteLinkView(APIView):
    permission_classes = [IsWorkspaceMember]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.invites import create_invite_link
        link = create_invite_link(
            workspace_id=request.workspace_id,
            created_by_id=request.user.id,
            subject_id=request.data.get("subject_id"),
            group_id=request.data.get("group_id"),
        )
        return Response({"token": link.token}, status=status.HTTP_201_CREATED)


class InviteLinkResolveView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "invite_link"

    def get(self, request: Request, token: str) -> Response:
        from apps.accounts.services.invites import resolve_invite_link
        data = resolve_invite_link(token)
        return Response(data)
