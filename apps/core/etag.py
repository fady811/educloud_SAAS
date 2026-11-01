"""ETag/If-None-Match helpers for polling endpoints (§19.4, REQ-COMM-03)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from django.http import HttpRequest
from rest_framework.response import Response


def compute_etag(data: Any) -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()  # noqa: S324


def add_etag(response: Response, etag: str) -> Response:
    response["ETag"] = f'"{etag}"'
    return response


def check_not_modified(request: HttpRequest, etag: str) -> bool:
    """Return True if the client's ETag matches — caller should return 304."""
    client_etag = request.headers.get("If-None-Match", "").strip('"')
    return bool(client_etag and client_etag == etag)
