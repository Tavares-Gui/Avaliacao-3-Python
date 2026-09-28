from rest_framework.routers import DefaultRouter

from .views import ClienteViewSet, OrdemServicoViewSet

router = DefaultRouter()
router.register("clientes", ClienteViewSet)
router.register("ordens", OrdemServicoViewSet, basename="ordem")
urlpatterns = router.urls
