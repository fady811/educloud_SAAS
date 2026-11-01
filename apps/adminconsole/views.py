"""Super-admin console views (Tier 11 — EduCloud staff only)."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsSuperAdmin


class WorkspaceListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request: Request) -> Response:
        from apps.workspaces.models import Workspace
        from apps.core.tenancy.managers import AllObjectsManager
        qs = Workspace.objects.using("default").order_by("-created_at")[:100]
        data = [
            {
                "id": ws.id,
                "subdomain": ws.subdomain,
                "status": ws.status,
                "created_at": ws.created_at.isoformat(),
            }
            for ws in qs
        ]
        return Response({"results": data})


class WorkspaceStatusView(APIView):
    """Force-transition a workspace status."""
    permission_classes = [IsSuperAdmin]

    def post(self, request: Request, pk: int) -> Response:
        from apps.workspaces.models import Workspace
        from apps.workspaces.services.lifecycle import transition
        from apps.core.errors import NotFound
        from apps.core.enums import ActorType

        try:
            ws = Workspace.objects.get(id=pk)
        except Workspace.DoesNotExist:
            raise NotFound("Workspace not found")

        transition(
            ws,
            request.data["status"],
            actor_type=ActorType.ADMIN,
            reason=request.data.get("reason", ""),
        )
        return Response({"id": ws.id, "status": ws.status})


class UserListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request: Request) -> Response:
        from apps.accounts.models import User
        qs = User.objects.filter(deleted_at__isnull=True).order_by("-created_at")[:100]
        data = [
            {
                "id": u.id,
                "email": u.email,
                "phone": u.phone,
                "display_name": u.display_name,
                "created_at": u.created_at.isoformat(),
            }
            for u in qs
        ]
        return Response({"results": data})


class PackageListCreateView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request: Request) -> Response:
        from apps.billing.models import Package
        qs = Package.objects.filter(is_active=True).order_by("display_order")
        data = [
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "price_egp": str(p.price_egp),
                "duration_months": p.duration_months,
            }
            for p in qs
        ]
        return Response({"results": data})

    def post(self, request: Request) -> Response:
        from apps.billing.models import Package
        from rest_framework import status as drf_status
        p = Package.objects.create(
            name=request.data["name"],
            slug=request.data["slug"],
            price_egp=request.data["price_egp"],
            duration_months=request.data.get("duration_months", 1),
            max_students=request.data.get("max_students"),
            storage_gb=request.data.get("storage_gb"),
            max_subjects_courses=request.data.get("max_subjects_courses"),
            max_groups=request.data.get("max_groups"),
            max_team_members=request.data.get("max_team_members"),
        )
        return Response({"id": p.id, "slug": p.slug}, status=drf_status.HTTP_201_CREATED)
