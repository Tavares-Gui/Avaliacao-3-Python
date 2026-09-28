from django.contrib import admin
from django.urls import include, path
from assistencia.painel import painel
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("", painel, name="painel"),
    path("admin/", admin.site.urls),
    path("api/", include("assistencia.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
handler500 = "assistencia.exceptions.server_error"
