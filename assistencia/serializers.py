from rest_framework import serializers

from .models import Cliente, OrdemServico


class ClienteResumoSerializer(serializers.ModelSerializer):
    """Resumo sem ordens, para não criar recursão no relacionamento."""

    class Meta:
        model = Cliente
        fields = ["id", "nome", "email", "telefone"]
        read_only_fields = fields


class OrdemResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdemServico
        fields = ["id", "equipamento", "status", "prioridade", "valor_estimado"]
        read_only_fields = fields


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ["id", "nome", "email", "telefone", "criado_em"]
        read_only_fields = ["id", "criado_em"]

    def validate_email(self, value):
        value = value.lower()
        clientes = Cliente.objects.filter(email__iexact=value)
        if self.instance:
            clientes = clientes.exclude(pk=self.instance.pk)
        if clientes.exists():
            raise serializers.ValidationError("Já existe um cliente com este e-mail.")
        return value


class ClienteDetalheSerializer(ClienteSerializer):
    ordens = OrdemResumoSerializer(many=True, read_only=True)

    class Meta(ClienteSerializer.Meta):
        fields = ClienteSerializer.Meta.fields + ["ordens"]


class OrdemServicoSerializer(serializers.ModelSerializer):
    # Na leitura, retorna o cliente aninhado. Na escrita, recebe só a chave.
    cliente = ClienteResumoSerializer(read_only=True)
    cliente_id = serializers.PrimaryKeyRelatedField(
        source="cliente", queryset=Cliente.objects.all(), write_only=True,
    )

    class Meta:
        model = OrdemServico
        fields = [
            "id", "cliente", "cliente_id", "equipamento", "descricao", "status",
            "prioridade", "valor_estimado", "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # Todos os campos editáveis são exigidos em POST/PUT. PATCH permite omissão.
        extra_kwargs = {
            "status": {"required": True},
            "prioridade": {"required": True},
            "valor_estimado": {"required": True},
        }


class ResumoOrdensSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    por_status = serializers.DictField(child=serializers.IntegerField())
    valor_total_estimado = serializers.DecimalField(max_digits=20, decimal_places=2)
