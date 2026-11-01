"""Support views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import WorkspacePermission, ALL_MEMBERS
from apps.accounts.enums import PermissionKey
from apps.support.serializers import TicketSerializer, TicketWriteSerializer, TicketMessageSerializer


class TicketListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"allowed_roles": ALL_MEMBERS},
    }

    def get(self, request: Request) -> Response:
        from apps.support.models import SupportTicket
        from apps.accounts.services.permissions import has_permission
        qs = SupportTicket.objects.filter(workspace_id=request.workspace_id)
        # Members see only their own tickets unless they have REPORTS_VIEW
        if not has_permission(request.user, request.workspace_id, PermissionKey.REPORTS_VIEW):
            qs = qs.filter(submitted_by_id=request.user.id)
        return Response(TicketSerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        from apps.support.models import SupportTicket
        ser = TicketWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ticket = SupportTicket.objects.create(
            workspace_id=request.workspace_id,
            submitted_by_id=request.user.id,
            **ser.validated_data,
        )
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class TicketDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "PATCH": {"allowed_roles": ALL_MEMBERS},
    }

    def _get(self, request, pk):
        from apps.support.models import SupportTicket
        from apps.core.errors import NotFound
        try:
            return SupportTicket.objects.get(id=pk, workspace_id=request.workspace_id)
        except SupportTicket.DoesNotExist:
            raise NotFound("Ticket not found")

    def _assert_own_or_reports(self, request, ticket):
        from apps.accounts.services.permissions import has_permission
        from apps.core.errors import PermissionDeniedError
        if ticket.submitted_by_id != request.user.id:
            if not has_permission(request.user, request.workspace_id, PermissionKey.REPORTS_VIEW):
                raise PermissionDeniedError("You may only access your own tickets.")

    def get(self, request: Request, pk: int) -> Response:
        ticket = self._get(request, pk)
        self._assert_own_or_reports(request, ticket)
        return Response(TicketSerializer(ticket).data)

    def patch(self, request: Request, pk: int) -> Response:
        ticket = self._get(request, pk)
        self._assert_own_or_reports(request, ticket)
        new_status = request.data.get("status")
        if new_status:
            ticket.status = new_status
            if new_status == "RESOLVED":
                from django.utils import timezone
                ticket.resolved_at = timezone.now()
            ticket.save()
        return Response(TicketSerializer(ticket).data)


class TicketMessageView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"allowed_roles": ALL_MEMBERS},
    }

    def post(self, request: Request, pk: int) -> Response:
        from apps.support.models import SupportTicket, TicketMessage
        from apps.core.errors import NotFound, PermissionDeniedError
        from apps.accounts.services.permissions import has_permission
        try:
            ticket = SupportTicket.objects.get(id=pk, workspace_id=request.workspace_id)
        except SupportTicket.DoesNotExist:
            raise NotFound("Ticket not found")
        # Only ticket owner or user with REPORTS_VIEW may add messages
        if ticket.submitted_by_id != request.user.id:
            if not has_permission(request.user, request.workspace_id, PermissionKey.REPORTS_VIEW):
                raise PermissionDeniedError("You may only message on your own tickets.")
        msg = TicketMessage.objects.create(
            workspace_id=request.workspace_id,
            ticket=ticket,
            author_id=request.user.id,
            body=request.data.get("body", ""),
        )
        return Response(TicketMessageSerializer(msg).data, status=status.HTTP_201_CREATED)
