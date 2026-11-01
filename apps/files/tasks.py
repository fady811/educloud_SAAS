"""File async tasks."""
from __future__ import annotations

from celery import shared_task


@shared_task(queue="files")
def scan_uploaded_file(file_id: int) -> None:
    from apps.files.models import StoredFile
    from apps.files.services.scanner import initiate_scan

    try:
        f = StoredFile.objects.get(id=file_id)
        initiate_scan(f)
    except StoredFile.DoesNotExist:
        pass


@shared_task(queue="files")
def sweep_orphaned_files() -> None:
    """Delete StoredFiles that are soft-deleted and have no references."""
    from apps.files.models import StoredFile
    from apps.files.services.storage import delete_object
    from django.utils import timezone
    import datetime

    cutoff = timezone.now() - datetime.timedelta(days=7)
    orphans = StoredFile.objects.filter(deleted_at__lte=cutoff)
    for f in orphans:
        try:
            delete_object(f.key)
        except Exception:
            pass
        f.delete()


@shared_task(queue="files")
def verify_stored_files_sample() -> None:
    """Spot-check that R2 objects still exist (REQ-FILE-09)."""
    import random
    from apps.files.models import StoredFile
    from apps.files.services.storage import object_exists

    qs = StoredFile.objects.filter(deleted_at__isnull=True)
    count = qs.count()
    if count == 0:
        return
    sample_ids = random.sample(list(qs.values_list("id", flat=True)), min(50, count))
    for f in StoredFile.objects.filter(id__in=sample_ids):
        if not object_exists(f.key):
            f.scan_result = (f.scan_result or {}) | {"missing": True}
            f.save(update_fields=["scan_result"])
