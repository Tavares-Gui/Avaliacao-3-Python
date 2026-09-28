"""Testa os formulários contra a API real em um servidor/banco descartáveis."""
from unittest.mock import patch
from urllib.error import URLError

from django.test import Client, LiveServerTestCase

from assistencia.models import Cliente, OrdemServico


class PainelTests(LiveServerTestCase):
    host = "127.0.0.1"

    def setUp(self):
        self.request_host = self.live_server_url.removeprefix("http://")
        self.ana = Cliente.objects.create(nome="Ana", email="ana@example.com", telefone="11999990001")

    def get(self, url="/"):
        return self.client.get(url, HTTP_HOST=self.request_host)

    def enviar(self, **dados):
        resposta = self.client.post("/", dados, HTTP_HOST=self.request_host)
        self.assertEqual(resposta.status_code, 302)
        # O navegador segue o redirecionamento sem repetir o POST.
        return self.get(resposta["Location"].split("#")[0])

    def test_pagina_sem_javascript_e_csrf_ativo(self):
        resposta = self.get()
        self.assertContains(resposta, "Bancada")
        self.assertContains(resposta, "200 OK")
        self.assertContains(resposta, "csrfmiddlewaretoken")
        self.assertNotContains(resposta, "<script")
        protegido = Client(enforce_csrf_checks=True)
        resposta = protegido.post("/", {"recurso": "clientes", "acao": "criar"}, HTTP_HOST=self.request_host)
        self.assertEqual(resposta.status_code, 403)

    def test_crud_cliente_e_prg_nao_repete_cadastro(self):
        dados = {"nome": "Marina", "email": "marina@example.com", "telefone": "11999990002"}
        resposta = self.enviar(recurso="clientes", acao="criar", **dados)
        self.assertContains(resposta, "201 Created")
        self.assertContains(resposta, "Cadastro realizado.")
        cliente = Cliente.objects.get(email=dados["email"])
        self.get("/?recurso=clientes")
        self.assertEqual(Cliente.objects.count(), 2)
        resposta = self.enviar(recurso="clientes", acao="editar", id=cliente.pk, **{**dados, "nome": "Marina Silva"})
        self.assertContains(resposta, "200 OK")
        cliente.refresh_from_db()
        self.assertEqual(cliente.nome, "Marina Silva")
        resposta = self.enviar(recurso="clientes", acao="parcial", id=cliente.pk, telefone="21999990002")
        self.assertContains(resposta, "PATCH")
        cliente.refresh_from_db()
        self.assertEqual(cliente.telefone, "21999990002")
        self.assertEqual(cliente.nome, "Marina Silva")
        resposta = self.enviar(recurso="clientes", acao="excluir", id=cliente.pk)
        self.assertContains(resposta, "204 No Content")
        self.assertContains(resposta, "corpo vazio")
        self.assertFalse(Cliente.objects.filter(pk=cliente.pk).exists())

    def test_erro_400_preserva_formulario_e_mostra_validacoes(self):
        resposta = self.enviar(recurso="clientes", acao="criar", nome="Marina", email="invalido", telefone="12")
        self.assertContains(resposta, "400 Bad Request")
        self.assertContains(resposta, 'value="Marina"')
        self.assertContains(resposta, 'value="invalido"')
        self.assertContains(resposta, "field-error")
        self.assertEqual(Cliente.objects.count(), 1)

    def test_ordem_crud_relacionamento_valor_negativo_e_protect(self):
        dados = dict(cliente_id=self.ana.pk, equipamento="Notebook", descricao="Não liga.",
                     status="aberta", prioridade="normal", valor_estimado="180.00")
        resposta = self.enviar(recurso="ordens", acao="criar", **dados)
        self.assertContains(resposta, "201 Created")
        ordem = OrdemServico.objects.get()
        detalhe = self.get(f"/?recurso=ordens&id={ordem.pk}")
        self.assertContains(detalhe, "Cliente vinculado")
        self.assertContains(detalhe, "ana@example.com")
        detalhe_cliente = self.get(f"/?recurso=clientes&id={self.ana.pk}")
        self.assertContains(detalhe_cliente, "Ordens deste cliente")
        self.assertContains(detalhe_cliente, "Notebook")
        resposta = self.enviar(recurso="ordens", acao="editar", id=ordem.pk, **{**dados, "valor_estimado": "-1"})
        self.assertContains(resposta, "400 Bad Request")
        self.assertContains(resposta, 'value="-1"')
        ordem.refresh_from_db()
        self.assertEqual(str(ordem.valor_estimado), "180.00")
        resposta = self.enviar(recurso="ordens", acao="editar", id=ordem.pk, **{**dados, "equipamento": "Monitor"})
        self.assertContains(resposta, "200 OK")
        ordem.refresh_from_db()
        self.assertEqual(ordem.equipamento, "Monitor")
        resposta = self.enviar(recurso="ordens", acao="parcial", id=ordem.pk, status="concluida")
        self.assertContains(resposta, "PATCH")
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, "concluida")
        resposta = self.enviar(recurso="clientes", acao="excluir", id=self.ana.pk)
        self.assertContains(resposta, "400 Bad Request")
        self.assertContains(resposta, "vinculadas")
        self.assertTrue(Cliente.objects.filter(pk=self.ana.pk).exists())
        resposta = self.enviar(recurso="ordens", acao="excluir", id=ordem.pk)
        self.assertContains(resposta, "204 No Content")
        self.assertFalse(OrdemServico.objects.filter(pk=ordem.pk).exists())

    def test_confirmacao_nao_exclui_em_get(self):
        resposta = self.get(f"/?recurso=clientes&id={self.ana.pk}&excluir=1")
        self.assertContains(resposta, "Confirmar exclusão")
        self.assertTrue(Cliente.objects.filter(pk=self.ana.pk).exists())

    def test_consulta_inexistente_mostra_404(self):
        resposta = self.get("/?recurso=clientes&id=999999")
        self.assertContains(resposta, "404 Not Found")
        self.assertNotContains(resposta, "Confirmar exclusão")

    def test_paginacao_filtros_e_cliente_alem_da_primeira_pagina(self):
        for i in range(11):
            Cliente.objects.create(nome=f"Cliente {i:02}", email=f"cliente{i}@example.com", telefone="11999990003")
        resposta = self.get("/?recurso=clientes&page=2&ordering=nome")
        self.assertEqual(len(resposta.context["registros"]), 2)
        self.assertContains(resposta, "Página 2")
        filtro = self.get("/?recurso=clientes&search=Cliente+10")
        self.assertEqual(filtro.context["total"], 1)
        painel_ordem = self.get("/")
        self.assertEqual(len(painel_ordem.context["clientes"]), 12)
        self.assertContains(painel_ordem, "Cliente 10")

    def test_conteudo_do_usuario_e_escapado(self):
        self.ana.nome = "<script>alert(1)</script>"
        self.ana.save()
        resposta = self.get(f"/?recurso=clientes&id={self.ana.pk}")
        self.assertNotContains(resposta, "<script>")
        self.assertContains(resposta, "&lt;script&gt;")

    def test_api_indisponivel_nao_inventa_codigo_http(self):
        with patch("assistencia.painel.build_opener") as opener:
            opener.return_value.open.side_effect = URLError("indisponível")
            resposta = self.get()
        self.assertContains(resposta, "Sem conexão")
        self.assertContains(resposta, "A API não respondeu")
        self.assertIsNone(resposta.context["resultado"]["status"])

