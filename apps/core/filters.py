"""Shared filter/order backends with allowlists (§14.5)."""
from __future__ import annotations

from rest_framework.filters import OrderingFilter


class AllowlistedOrderingFilter(OrderingFilter):
    """Ordering filter that requires an explicit ordering_fields allowlist."""

    def get_ordering(self, request: object, queryset: object, view: object) -> list[str]:
        if not getattr(view, "ordering_fields", None):
            return []
        return super().get_ordering(request, queryset, view) or []
