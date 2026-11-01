"""
CSV student import with mandatory partial success (REQ-CONTENT-08a).
Per-row savepoints — never one transaction for the whole file.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.core.errors import LimitExceeded, ValidationFailed
from apps.core.validators import normalize_phone, validate_phone
from apps.core.enums import Role


def import_students(
    *,
    workspace_id: int,
    created_by_id: int,
    csv_content: bytes,
    default_group_id: int | None = None,
) -> "StudentImportJob":  # type: ignore[name-defined]
    """
    Parse and import a CSV of students. Valid rows are created even when others fail.
    Returns the StudentImportJob with per-row outcomes.
    """
    from apps.accounts.models import StudentImportJob, StudentImportRow

    rows = _parse_csv(csv_content)
    job = StudentImportJob.objects.create(
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        total_rows=len(rows),
        status="PROCESSING",
    )

    created = 0
    skipped = 0

    for i, row_data in enumerate(rows, start=1):
        row_result = _import_row(job, i, row_data, workspace_id, default_group_id)
        StudentImportRow.objects.create(
            job=job,
            row_number=i,
            raw_data=row_data,
            **row_result,
        )
        if row_result["status"] == "CREATED":
            created += 1
        else:
            skipped += 1

    # Final job summary — wraps only the job update, not the whole import
    with transaction.atomic():
        job.created_count = created
        job.skipped_count = skipped
        job.status = "DONE"
        job.save(update_fields=["created_count", "skipped_count", "status", "updated_at"])

    return job


def _import_row(
    job: object,
    row_num: int,
    data: dict[str, Any],
    workspace_id: int,
    group_id: int | None,
) -> dict[str, Any]:
    from apps.accounts.models import User
    from apps.workspaces.models import WorkspaceMembership

    try:
        with transaction.atomic():
            name = data.get("name", "").strip()
            phone = data.get("phone", "").strip()
            email = data.get("email", "").strip() or None

            if not name:
                return {"status": "SKIPPED", "error_code": "MISSING_NAME", "error_detail": "Row is missing a name.", "created_user": None}
            if not phone:
                return {"status": "SKIPPED", "error_code": "MISSING_PHONE", "error_detail": "Row is missing a phone number.", "created_user": None}

            try:
                phone = normalize_phone(phone)
                validate_phone(phone)
            except Exception:
                return {"status": "SKIPPED", "error_code": "INVALID_PHONE", "error_detail": f"Invalid phone: {phone}", "created_user": None}

            if User.objects.filter(phone=phone).exists():
                return {"status": "SKIPPED", "error_code": "DUPLICATE_PHONE", "error_detail": "Phone already registered.", "created_user": None}

            if email and User.objects.filter(email__iexact=email).exists():
                return {"status": "SKIPPED", "error_code": "DUPLICATE_EMAIL", "error_detail": "Email already registered.", "created_user": None}

            parts = name.split(" ", 1)
            user = User(
                phone=phone,
                email=email,
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
            )
            user.set_unusable_password()
            user.save()

            WorkspaceMembership.objects.create(
                user=user,
                workspace_id=workspace_id,
                role=Role.STUDENT,
                is_owner=False,
            )

            return {"status": "CREATED", "error_code": "", "error_detail": "", "created_user": user}

    except Exception as e:  # noqa: BLE001
        return {"status": "SKIPPED", "error_code": "UNEXPECTED_ERROR", "error_detail": str(e), "created_user": None}


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")  # BOM-safe
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append({k.strip().lower(): v.strip() for k, v in row.items()})
        if len(rows) >= settings.CSV_IMPORT_ROW_LIMIT:
            break
    return rows
