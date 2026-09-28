from django.core.management.base import BaseCommand
from django.db import transaction

from assistencia.models import Cliente, OrdemServico


class Command(BaseCommand):
    help = "Cria dados fictícios de demonstração sem apagar ou alterar registros existentes."

    @transaction.atomic
    def handle(self, *args, **options):
        clientes = [
            ("Ana Demo", "ana.demo@example.com", "11999990001"),
            ("Bruno Demo", "bruno.demo@example.com", "21999990002"),
            ("Carla Demo", "carla.demo@example.com", "31999990003"),
        ]
        equipamentos = ["Notebook", "Impressora", "Monitor", "Computador"]
        criados = 0
        for i, (nome, email, telefone) in enumerate(clientes):
            cliente, _ = Cliente.objects.get_or_create(
                email=email, defaults={"nome": nome, "telefone": telefone},
            )
            for j, equipamento in enumerate(equipamentos):
                _, nova = OrdemServico.objects.get_or_create(
                    cliente=cliente,
                    equipamento=f"{equipamento} Demo {i + 1}",
                    defaults={
                        "descricao": "Diagnóstico e manutenção preventiva do equipamento de demonstração.",
                        "status": OrdemServico.Status.values[j],
                        "prioridade": OrdemServico.Prioridade.values[i],
                        "valor_estimado": str(100 + 50 * j),
                    },
                )
                criados += nova
        self.stdout.write(self.style.SUCCESS(f"Dados de demonstração disponíveis. Novas ordens: {criados}."))
