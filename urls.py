from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from printer.views import agent_dashboard, HealthCheckView

urlpatterns = [
    path("", agent_dashboard, name="agent-home"),
    path("agent/", agent_dashboard, name="agent-dashboard"),
    path("admin/", admin.site.urls),
    path("api/v2/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/v2/", include("printer.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
