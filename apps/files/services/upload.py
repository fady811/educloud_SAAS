"""File upload orchestration (REQ-FILE-01..05)."""
from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from apps.core.enums import FileCategory, ScanStatus
from apps.core.errors import ValidationFailed


MAX_UPLOAD_SIZES = {
    FileCategory.LESSON_VIDEO: 2 * 1024 ** 3,       # 2 GB
    FileCategory.LESSON_DOCUMENT: 50 * 1024 ** 2,    # 50 MB
    FileCategory.LESSON_ATTACHMENT: 50 * 1024 ** 2,
    FileCategory.PAYMENT_PROOF: 5 * 1024 ** 2,
    FileCategory.ASSIGNMENT_SUBMISSION: 50 * 1024 ** 2,
    FileCategory.BRANDING_LOGO: 5 * 1024 ** 2,
    FileCategory.ANNOUNCEMENT_ATTACHMENT: 20 * 1024 ** 2,
    FileCategory.MESSAGE_ATTACHMENT: 20 * 1024 ** 2,
}

ALLOWED_CONTENT_TYPES = {
    FileCategory.LESSON_VIDEO: {"video/mp4", "video/webm"},
    FileCategory.LESSON_DOCUMENT: {"application/pdf", "application/msword",
                                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    FileCategory.LESSON_ATTACHMENT: {"application/pdf", "image/jpeg", "image/png", "image/webp"},
    FileCategory.PAYMENT_PROOF: {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    FileCategory.ASSIGNMENT_SUBMISSION: {"application/pdf", "image/jpeg", "image/png"},
    FileCategory.BRANDING_LOGO: {"image/jpeg", "image/png", "image/webp"},
    FileCategory.ANNOUNCEMENT_ATTACHMENT: {"image/jpeg", "image/png", "application/pdf"},
    FileCategory.MESSAGE_ATTACHMENT: {"image/jpeg", "image/png", "application/pdf"},
}


def request_upload(
    *,
    workspace_id: int,
    uploaded_by_id: int,
    original_name: str,
    content_type: str,
    size_bytes: int,
    category: str,
) -> dict:
    """Issue presigned upload URL and create StoredFile in PENDING state."""
    from apps.files.models import StoredFile
    from apps.files.services.storage import get_storage

    allowed_types = ALLOWED_CONTENT_TYPES.get(category, set())
    if content_type not in allowed_types:
        raise ValidationFailed(f"Content type {content_type} not allowed for {category}.")

    max_size = MAX_UPLOAD_SIZES.get(category, 10 * 1024 ** 2)
    if size_bytes > max_size:
        raise ValidationFailed(f"File size exceeds limit for {category}.")

    ext = original_name.rsplit(".", 1)[-1] if "." in original_name else ""
    key = f"{workspace_id}/{category}/{uuid.uuid4().hex}.{ext}"

    with transaction.atomic():
        stored = StoredFile.objects.create(
            workspace_id=workspace_id,
            key=key,
            original_name=original_name,
            content_type=content_type,
            size_bytes=size_bytes,
            category=category,
            scan_status=ScanStatus.PENDING,
            uploaded_by_id=uploaded_by_id,
        )

    storage = get_storage()
    presign = storage.presign_upload(key, content_type, size_bytes)
    return {"file_id": stored.id, "upload": presign}


def confirm_upload(file_id: int) -> None:
    """Called after client confirms upload complete; triggers async scan."""
    from apps.files.tasks import scan_uploaded_file
    scan_uploaded_file.apply_async(args=[file_id], queue="files")


def issue_download_url(file_id: int, *, requester_id: int, workspace_id: int) -> str:
    from apps.files.models import StoredFile
    from apps.files.services.storage import get_storage
    from apps.core.errors import NotFound, PermissionDeniedError

    try:
        f = StoredFile.objects.get(id=file_id, deleted_at__isnull=True)
    except StoredFile.DoesNotExist:
        raise NotFound("File not found.")

    if not f.is_public and f.workspace_id != workspace_id:
        raise PermissionDeniedError("File not accessible.")

    return get_storage().issue_download_url(f.key, f.original_name)
