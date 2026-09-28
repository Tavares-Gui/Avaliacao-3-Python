from django.contrib import admin

from .models import Cliente, OrdemServico


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["id", "nome", "email", "telefone"]
    search_fields = ["nome", "email"]
    readonly_fields = ["criado_em"]


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ["id", "equipamento", "cliente", "status", "prioridade", "valor_estimado"]
    list_filter = ["status", "prioridade"]
    search_fields = ["equipamento", "cliente__nome"]
    list_select_related = ["cliente"]
    readonly_fields = ["criado_em", "atualizado_em"]
