"""File upload/management views."""
from __future__ import annotations

import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsWorkspaceMember
from apps.files.serializers import StoredFileSerializer, UploadRequestSerializer


class UploadRequestView(APIView):
    """Request a presigned upload URL."""
    permission_classes = [IsWorkspaceMember]

    def post(self, request: Request) -> Response:
        from apps.files.services.upload import request_upload
        ser = UploadRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data.copy()
        data["original_name"] = data.pop("filename")
        result = request_upload(
            workspace_id=request.workspace_id,
            uploaded_by_id=request.user.id,
            **data,
        )
        return Response(result, status=status.HTTP_201_CREATED)


class FileDetailView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request: Request, pk: int) -> Response:
        from apps.files.models import StoredFile
        from apps.core.errors import NotFound
        try:
            f = StoredFile.objects.get(id=pk, workspace_id=request.workspace_id, deleted_at__isnull=True)
        except StoredFile.DoesNotExist:
            raise NotFound("File not found")
        return Response(StoredFileSerializer(f).data)

    def delete(self, request: Request, pk: int) -> Response:
        from apps.files.models import StoredFile
        from apps.core.errors import NotFound
        from django.utils import timezone
        try:
            f = StoredFile.objects.get(id=pk, workspace_id=request.workspace_id, deleted_at__isnull=True)
        except StoredFile.DoesNotExist:
            raise NotFound("File not found")
        f.deleted_at = timezone.now()
        f.save(update_fields=["deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileScanCallbackView(APIView):
    """Internal callback from scanner — validate shared secret, no user auth."""
    permission_classes = []
    authentication_classes = []

    def post(self, request: Request, pk: int) -> Response:
        secret = getattr(settings, "SCANNER_CALLBACK_SECRET", "")
        if not secret:
            # If no secret is configured, reject all callbacks (fail-closed)
            return Response({"error": "Callback endpoint not configured."}, status=status.HTTP_403_FORBIDDEN)

        provided = request.headers.get("X-Scanner-Secret", "")
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(provided.encode(), secret.encode()):
            return Response({"error": "Invalid secret."}, status=status.HTTP_403_FORBIDDEN)

        from apps.files.services.scanner import process_scan_result
        process_scan_result(file_id=pk, result=request.data)
        return Response({"ok": True})
