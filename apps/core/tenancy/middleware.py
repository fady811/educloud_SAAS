"""TenantResolverMiddleware — resolves workspace from subdomain or custom domain (§15.2)."""
from __future__ import annotations

import logging
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.core.tenancy.context import set_current_workspace

logger = logging.getLogger(__name__)


class TenantResolverMiddleware:
    """
    Resolves the workspace from the request host.
    Sets the tenant context so TenantManager filters automatically.

    Resolution order (§15.2a):
      1. X-Workspace-ID header (for internal/admin requests — only on platform host)
      2. Subdomain: <slug>.BASE_DOMAIN
      3. Custom domain: exact match in custom_domains table
      4. No workspace (platform host) — Super Admin API paths are served here
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        workspace_id = self._resolve(request)
        set_current_workspace(workspace_id)
        request.workspace_id = workspace_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        set_current_workspace(None)
        return response

    def _resolve(self, request: HttpRequest) -> int | None:
        host = request.get_host().split(":")[0].lower()
        base = getattr(settings, "BASE_DOMAIN", "educloud.app")
        suffix = f".{base}"

        # Subdomain resolution
        if host.endswith(suffix):
            slug = host[: -len(suffix)]
            if slug and slug not in ("api", "admin", "www", "app", "static", "mail"):
                return self._workspace_id_for_slug(slug)

        # Custom domain resolution
        if host != base:
            return self._workspace_id_for_custom_domain(host)

        return None  # Platform host

    @staticmethod
    def _workspace_id_for_slug(slug: str) -> int | None:
        try:
            from apps.workspaces.models import Workspace  # lazy import — no cycle
            ws = Workspace.objects.filter(subdomain=slug, deleted_at__isnull=True).only("id").first()
            return ws.id if ws else None
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _workspace_id_for_custom_domain(domain: str) -> int | None:
        try:
            from apps.workspaces.models import CustomDomain  # lazy import
            cd = CustomDomain.objects.filter(domain=domain, status="ACTIVE").only("workspace_id").first()
            return cd.workspace_id if cd else None
        except Exception:  # noqa: BLE001
            return None
