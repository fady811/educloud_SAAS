"""Root URL configuration (§8.1)."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # --- Tenant (workspace) API ---
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.workspaces.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.files.urls")),
    path("api/v1/", include("apps.content.urls")),
    path("api/v1/", include("apps.groups.urls")),
    path("api/v1/", include("apps.enrollment.urls")),
    path("api/v1/", include("apps.assessments.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.communication.urls")),
    path("api/v1/", include("apps.parents.urls")),
    path("api/v1/", include("apps.reports.urls")),
    path("api/v1/", include("apps.support.urls")),

    # --- Platform Admin API (§15.5 — served on platform host) ---
    path("api/v1/admin/", include("apps.adminconsole.urls")),

    # --- Health ---
    path("health/", include("apps.core.health_urls")),

    # --- OpenAPI schema ---
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
