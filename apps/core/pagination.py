"""Pagination classes (§14)."""
from __future__ import annotations

from rest_framework.pagination import (
    CursorPagination as DRFCursorPagination,
    PageNumberPagination as DRFPageNumberPagination,
)
from rest_framework.response import Response


class PageNumberPagination(DRFPageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
    page_query_param = "page"

    def get_paginated_response(self, data: object) -> Response:
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })


class CursorPagination(DRFCursorPagination):
    """Cursor pagination for append-heavy lists like messages (§14.4)."""
    page_size = 50
    ordering = "-created_at"
    cursor_query_param = "cursor"
