"""RequestIdMiddleware and ReadOnlyWorkspaceMiddleware (§21.3, §6.1)."""
from __future__ import annotations

import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse

from apps.core.logging import set_request_id, get_request_id


class RequestIdMiddleware:
    """Attaches a request ID from the header or generates one (§21.3)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        request.request_id = request_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class ReadOnlyWorkspaceMiddleware:
    """
    Returns 503 for write requests when the workspace is in read-only maintenance mode.
    Currently a no-op placeholder for the hook (§21.2).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)
