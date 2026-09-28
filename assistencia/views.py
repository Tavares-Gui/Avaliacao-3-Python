from decimal import Decimal

from django.db.models import Count, Sum
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import ClienteFilter, OrdemServicoFilter
from .models import Cliente, OrdemServico
from .serializers import (
    ClienteDetalheSerializer, ClienteSerializer, OrdemServicoSerializer, ResumoOrdensSerializer,
)


class ClienteViewSet(ModelViewSet):
    """CRUD de clientes; o detalhe também apresenta as ordens vinculadas."""
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    filterset_class = ClienteFilter
    search_fields = ["nome", "email"]
    ordering_fields = ["nome", "criado_em", "id"]
    ordering = ["nome", "id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return queryset.prefetch_related("ordens")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ClienteDetalheSerializer
        return ClienteSerializer


class OrdemServicoViewSet(ModelViewSet):
    """CRUD de ordens de serviço, com cliente aninhado na resposta."""
    queryset = OrdemServico.objects.select_related("cliente").all()
    serializer_class = OrdemServicoSerializer
    filterset_class = OrdemServicoFilter
    search_fields = ["equipamento", "descricao", "cliente__nome"]
    ordering_fields = ["criado_em", "valor_estimado", "id"]
    ordering = ["-criado_em", "-id"]

    @extend_schema(responses=ResumoOrdensSerializer)
    @action(detail=False, methods=["get"], pagination_class=None)
    def resumo(self, request):
        """Resumo de todas as ordens que atendem aos filtros, antes da paginação."""
        ordens = self.filter_queryset(self.get_queryset())
        totais = ordens.aggregate(total=Count("id"), valor=Sum("valor_estimado"))
        por_status = dict.fromkeys(OrdemServico.Status.values, 0)
        grupos = ordens.order_by().values("status").annotate(total=Count("id"))
        for grupo in grupos:
            por_status[grupo["status"]] = grupo["total"]
        dados = {
            "total": totais["total"],
            "por_status": por_status,
            "valor_total_estimado": totais["valor"] or Decimal("0.00"),
        }
        return Response(ResumoOrdensSerializer(dados).data)
