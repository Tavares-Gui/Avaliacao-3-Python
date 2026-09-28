from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


class Cliente(models.Model):
    nome = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    telefone = models.CharField(
        max_length=11,
        validators=[RegexValidator(r"\A[0-9]{10,11}\Z", "Use DDD e número: 10 ou 11 dígitos, sem formatação.")],
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome", "id"]
        constraints = [
            models.UniqueConstraint(models.functions.Lower("email"), name="cliente_email_sem_distincao_caixa"),
        ]

    def __str__(self):
        return self.nome


class OrdemServico(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="ordens")
    equipamento = models.CharField(max_length=120)
    descricao = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTA)
    prioridade = models.CharField(max_length=10, choices=Prioridade.choices, default=Prioridade.NORMAL)
    valor_estimado = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "ordem de serviço"
        verbose_name_plural = "ordens de serviço"
        constraints = [
            models.CheckConstraint(condition=models.Q(valor_estimado__gte=0), name="ordem_valor_nao_negativo"),
            models.CheckConstraint(condition=models.Q(status__in=["aberta", "em_andamento", "concluida", "cancelada"]), name="ordem_status_valido"),
            models.CheckConstraint(condition=models.Q(prioridade__in=["baixa", "normal", "alta"]), name="ordem_prioridade_valida"),
        ]

    def __str__(self):
        return f"OS #{self.pk} - {self.equipamento}"
