import django_filters

from .models import Cliente, OrdemServico


class ClienteFilter(django_filters.FilterSet):
    nome = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Cliente
        fields = ["nome", "email"]


class OrdemServicoFilter(django_filters.FilterSet):
    class Meta:
        model = OrdemServico
        fields = ["cliente", "status", "prioridade"]
