"""Domain error hierarchy and DRF exception handler (§7.8)."""
from __future__ import annotations

import logging
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.enums import ErrorCode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class DomainError(Exception):
    """Base class for all business exceptions."""

    code: str = ErrorCode.INTERNAL_ERROR
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."

    def __init__(
        self,
        detail: str | None = None,
        code: str | None = None,
        **extra: Any,
    ) -> None:
        self.detail = detail or self.__class__.detail
        self.code = code or self.__class__.code
        self.extra = extra
        super().__init__(self.detail)


class ValidationFailed(DomainError):
    code = ErrorCode.VALIDATION_ERROR
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation failed."


class NotFound(DomainError):
    code = ErrorCode.NOT_FOUND
    http_status = status.HTTP_404_NOT_FOUND
    detail = "Not found."


class PermissionDeniedError(DomainError):
    code = ErrorCode.PERMISSION_DENIED
    http_status = status.HTTP_403_FORBIDDEN
    detail = "Permission denied."


class Conflict(DomainError):
    code = ErrorCode.CONFLICT
    http_status = status.HTTP_409_CONFLICT
    detail = "Conflict."


class LimitExceeded(DomainError):
    code = ErrorCode.LIMIT_EXCEEDED
    http_status = status.HTTP_409_CONFLICT
    detail = "A platform limit has been exceeded."

    def __init__(
        self,
        limit_key: str,
        limit: int | float,
        current: int | float,
        remedy: str = "",
        **extra: Any,
    ) -> None:
        super().__init__(self.detail, **extra)
        self.limit_key = limit_key
        self.limit = limit
        self.current = current
        self.remedy = remedy


class ThrottledError(DomainError):
    code = ErrorCode.LOGIN_BLOCKED
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Too many requests."

    def __init__(self, retry_after: int | None = None, **extra: Any) -> None:
        super().__init__(self.detail, **extra)
        self.retry_after = retry_after


class ExternalServiceError(DomainError):
    code = ErrorCode.EXTERNAL_SERVICE_ERROR
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "An external service is temporarily unavailable."


# ---------------------------------------------------------------------------
# DRF exception handler
# ---------------------------------------------------------------------------

def _build_error_body(code: str, detail: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "detail": detail}}
    if extra:
        body["error"].update(extra)
    return body


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Single DRF exception handler — maps domain and DRF exceptions to the envelope (§13.4)."""
    from apps.core.logging import get_request_id

    request = context.get("request")
    request_id = get_request_id()

    # --- Domain errors ---
    if isinstance(exc, DomainError):
        extra: dict[str, Any] = {}
        if isinstance(exc, LimitExceeded):
            extra = {"limit_key": exc.limit_key, "limit": exc.limit, "current": exc.current, "remedy": exc.remedy}
        elif isinstance(exc, ThrottledError) and exc.retry_after:
            extra = {"retry_after": exc.retry_after}
        extra.update(exc.extra or {})
        body = _build_error_body(exc.code, exc.detail, extra if extra else None)
        body["request_id"] = request_id
        return Response(body, status=exc.http_status)

    # --- DRF built-in errors ---
    response = drf_exception_handler(exc, context)

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        body = _build_error_body("AUTHENTICATION_REQUIRED", str(exc.detail))
        body["request_id"] = request_id
        return Response(body, status=exc.status_code)

    if isinstance(exc, PermissionDenied):
        body = _build_error_body(ErrorCode.PERMISSION_DENIED, str(exc.detail))
        body["request_id"] = request_id
        return Response(body, status=exc.status_code)

    if isinstance(exc, DRFValidationError):
        body = _build_error_body(ErrorCode.VALIDATION_ERROR, "Validation error.", {"fields": exc.detail})
        body["request_id"] = request_id
        return Response(body, status=exc.status_code)

    if isinstance(exc, Throttled):
        body = _build_error_body(ErrorCode.LOGIN_BLOCKED, "Too many requests.", {"retry_after": exc.wait})
        body["request_id"] = request_id
        return Response(body, status=status.HTTP_429_TOO_MANY_REQUESTS)

    if isinstance(exc, Http404):
        body = _build_error_body(ErrorCode.NOT_FOUND, "Not found.")
        body["request_id"] = request_id
        return Response(body, status=status.HTTP_404_NOT_FOUND)

    if response is not None:
        response.data = _build_error_body(ErrorCode.VALIDATION_ERROR, str(exc), response.data)
        response.data["request_id"] = request_id
        return response

    # Unhandled — 500 with opaque body (§21.2 — never leak stack traces)
    logger.exception("Unhandled exception", exc_info=exc, extra={"request_id": request_id})
    body = _build_error_body(ErrorCode.INTERNAL_ERROR, "An unexpected error occurred.")
    body["request_id"] = request_id
    return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
