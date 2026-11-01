"""CSV export service."""
from __future__ import annotations

import csv
import io

from apps.reports.registry import get


def generate_csv(name: str, workspace_id: int) -> str:
    reg = get(name)
    model_class = reg["model_class"]
    fields = reg["fields"]
    qs = model_class.objects.filter(workspace_id=workspace_id).values(*fields)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in qs:
        writer.writerow(row)
    return buf.getvalue()
