from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from assistencia.models import Cliente, OrdemServico


class APIBase(APITestCase):
    def setUp(self):
        self.ana = Cliente.objects.create(
            nome="Ana", email="ana@example.com", telefone="11999990001"
        )
        self.bruno = Cliente.objects.create(
            nome="Bruno", email="bruno@example.com", telefone="21999990002"
        )

    def payload_ordem(self, **alteracoes):
        dados = {
            "cliente_id": self.ana.pk,
            "equipamento": "Notebook",
            "descricao": "Não liga.",
            "status": "aberta",
            "prioridade": "normal",
            "valor_estimado": "150.00",
        }
        return {**dados, **alteracoes}

    def criar_ordem(self, **alteracoes):
        return OrdemServico.objects.create(**self.payload_ordem(**alteracoes))


class ClienteAPITests(APIBase):
    def test_crud_completo(self):
        dados = {"nome": "Carla", "email": "carla@example.com", "telefone": "31999990003"}
        resposta = self.client.post("/api/clientes/", dados, format="json")
        self.assertEqual(resposta.status_code, 201)
        url = f"/api/clientes/{resposta.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/api/clientes/").data["count"], 3)
        dados["nome"] = "Carla Souza"
        resposta = self.client.put(url, dados, format="json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["nome"], "Carla Souza")
        resposta = self.client.patch(url, {"nome": "Carla Silva"}, format="json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["email"], "carla@example.com")
        self.assertEqual(resposta.data["nome"], "Carla Silva")
        resposta = self.client.delete(url)
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(resposta.content, b"")
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_put_exige_todos_os_campos(self):
        resposta = self.client.put(f"/api/clientes/{self.ana.pk}/", {"nome": "Ana"}, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("email", resposta.data)
        self.assertIn("telefone", resposta.data)

    def test_validacoes(self):
        base = {"nome": "Carla", "email": "carla@example.com", "telefone": "31999990003"}
        for campo, valor in [
            ("nome", " "), ("email", "invalido"), ("email", "ANA@example.com"),
            ("telefone", "123"), ("telefone", "abcdefghijk"),
        ]:
            with self.subTest(campo=campo, valor=valor):
                resposta = self.client.post("/api/clientes/", {**base, campo: valor}, format="json")
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(campo, resposta.data)

    def test_email_normalizado_e_atualizacao_do_proprio_email(self):
        resposta = self.client.patch(
            f"/api/clientes/{self.ana.pk}/", {"email": "ANA@EXAMPLE.COM"}, format="json"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["email"], "ana@example.com")

    def test_patch_nao_permite_email_de_outro_cliente(self):
        resposta = self.client.patch(
            f"/api/clientes/{self.bruno.pk}/", {"email": "ANA@example.com"}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)
        self.bruno.refresh_from_db()
        self.assertEqual(self.bruno.email, "bruno@example.com")

    def test_detalhe_aninha_ordens_sem_ciclo(self):
        ordem = self.criar_ordem()
        resposta = self.client.get(f"/api/clientes/{self.ana.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["ordens"][0]["id"], ordem.pk)
        self.assertNotIn("cliente", resposta.data["ordens"][0])

    def test_exclusao_protegida_e_liberada_apos_remover_ordem(self):
        ordem = self.criar_ordem()
        url = f"/api/clientes/{self.ana.pk}/"
        resposta = self.client.delete(url)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("vinculadas", resposta.data["detail"])
        self.assertTrue(Cliente.objects.filter(pk=self.ana.pk).exists())
        self.assertTrue(OrdemServico.objects.filter(pk=ordem.pk).exists())
        self.assertEqual(self.client.delete(f"/api/ordens/{ordem.pk}/").status_code, 204)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_filtros_busca_e_ordenacao(self):
        for consulta in ["nome=an", "email=ANA@example.com", "search=Ana"]:
            with self.subTest(consulta=consulta):
                resposta = self.client.get(f"/api/clientes/?{consulta}")
                self.assertEqual(resposta.data["count"], 1)
                self.assertEqual(resposta.data["results"][0]["id"], self.ana.pk)
        resposta = self.client.get("/api/clientes/?ordering=-nome")
        self.assertEqual(resposta.data["results"][0]["id"], self.bruno.pk)

    def test_paginacao(self):
        for i in range(10):
            Cliente.objects.create(nome=f"Cliente {i}", email=f"c{i}@example.com", telefone="11999990000")
        primeira = self.client.get("/api/clientes/")
        segunda = self.client.get("/api/clientes/?page=2")
        self.assertEqual(primeira.data["count"], 12)
        self.assertEqual(len(primeira.data["results"]), 10)
        self.assertIsNotNone(primeira.data["next"])
        self.assertEqual(len(segunda.data["results"]), 2)


class OrdemAPITests(APIBase):
    def test_crud_completo_com_cliente_aninhado_e_troca_de_cliente(self):
        resposta = self.client.post("/api/ordens/", self.payload_ordem(), format="json")
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.data["cliente"]["id"], self.ana.pk)
        self.assertNotIn("cliente_id", resposta.data)
        url = f"/api/ordens/{resposta.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/api/ordens/").data["count"], 1)
        dados = self.payload_ordem(cliente_id=self.bruno.pk, equipamento="Monitor", valor_estimado="250.50")
        resposta = self.client.put(url, dados, format="json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["cliente"]["id"], self.bruno.pk)
        self.assertEqual(resposta.data["equipamento"], "Monitor")
        self.assertEqual(resposta.data["valor_estimado"], "250.50")
        resposta = self.client.patch(url, {"status": "concluida"}, format="json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["status"], "concluida")
        self.assertEqual(resposta.data["equipamento"], "Monitor")
        resposta = self.client.delete(url)
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(resposta.content, b"")
        self.assertTrue(Cliente.objects.filter(pk=self.bruno.pk).exists())
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_put_exige_todos_os_campos_inclusive_aqueles_com_default_no_model(self):
        ordem = self.criar_ordem()
        for campo in self.payload_ordem():
            with self.subTest(campo=campo):
                dados = self.payload_ordem()
                dados.pop(campo)
                resposta = self.client.put(f"/api/ordens/{ordem.pk}/", dados, format="json")
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(campo, resposta.data)

    def test_payloads_invalidos_nao_criam_ordens(self):
        for campo, valor in [
            ("cliente_id", 999999), ("cliente_id", "texto"), ("cliente_id", None),
            ("equipamento", ""), ("descricao", " "), ("status", "desconhecido"),
            ("prioridade", "urgente"), ("valor_estimado", "-0.01"),
            ("valor_estimado", "1.999"), ("valor_estimado", "abc"),
            ("valor_estimado", "100000000.00"),
        ]:
            with self.subTest(campo=campo, valor=valor):
                resposta = self.client.post(
                    "/api/ordens/", self.payload_ordem(**{campo: valor}), format="json"
                )
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(campo, resposta.data)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_patch_invalido_preserva_valor(self):
        ordem = self.criar_ordem()
        resposta = self.client.patch(f"/api/ordens/{ordem.pk}/", {"valor_estimado": "-1"}, format="json")
        self.assertEqual(resposta.status_code, 400)
        ordem.refresh_from_db()
        self.assertEqual(ordem.valor_estimado, Decimal("150.00"))

    def test_zero_e_valor_maximo_sao_aceitos(self):
        for valor in ["0.00", "99999999.99"]:
            with self.subTest(valor=valor):
                resposta = self.client.post("/api/ordens/", self.payload_ordem(valor_estimado=valor), format="json")
                self.assertEqual(resposta.status_code, 201)
                self.assertEqual(resposta.data["valor_estimado"], valor)

    def test_campos_de_auditoria_nao_podem_ser_editados(self):
        ordem = self.criar_ordem()
        original = ordem.criado_em
        resposta = self.client.patch(
            f"/api/ordens/{ordem.pk}/", {"id": 999999, "criado_em": "2000-01-01T00:00:00Z"}, format="json"
        )
        self.assertEqual(resposta.status_code, 200)
        ordem.refresh_from_db()
        self.assertEqual(ordem.criado_em, original)
        self.assertEqual(resposta.data["id"], ordem.pk)

    def test_filtros_busca_e_ordenacao(self):
        ordem = self.criar_ordem(prioridade="alta")
        self.criar_ordem(cliente_id=self.bruno.pk, equipamento="Monitor", status="concluida", valor_estimado="50.00")
        for consulta in [f"cliente={self.ana.pk}", "status=aberta", "prioridade=alta", "search=Notebook", "search=Ana"]:
            with self.subTest(consulta=consulta):
                resposta = self.client.get(f"/api/ordens/?{consulta}")
                self.assertEqual(resposta.data["count"], 1)
                self.assertEqual(resposta.data["results"][0]["id"], ordem.pk)
        resposta = self.client.get("/api/ordens/?ordering=-valor_estimado")
        self.assertEqual(resposta.data["results"][0]["id"], ordem.pk)

    def test_filtros_invalidos(self):
        for consulta in ["cliente=texto", "cliente=999999", "status=inexistente", "prioridade=invalida"]:
            with self.subTest(consulta=consulta):
                self.assertEqual(self.client.get(f"/api/ordens/?{consulta}").status_code, 400)

    def test_paginacao(self):
        for i in range(12):
            self.criar_ordem(equipamento=f"Notebook {i}")
        primeira = self.client.get("/api/ordens/")
        segunda = self.client.get("/api/ordens/?page=2")
        self.assertEqual(primeira.data["count"], 12)
        self.assertEqual(len(primeira.data["results"]), 10)
        self.assertEqual(len(segunda.data["results"]), 2)
        self.assertTrue({x["id"] for x in primeira.data["results"]}.isdisjoint(x["id"] for x in segunda.data["results"]))

    def test_cliente_aninhado_nao_provoca_consulta_por_ordem(self):
        for i in range(5):
            self.criar_ordem(equipamento=f"Notebook {i}")
        # Uma consulta COUNT da paginação e uma consulta com JOIN.
        with self.assertNumQueries(2):
            resposta = self.client.get("/api/ordens/")
        self.assertEqual(len(resposta.data["results"]), 5)

    def test_resumo_vazio(self):
        resposta = self.client.get("/api/ordens/resumo/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["total"], 0)
        self.assertEqual(resposta.data["valor_total_estimado"], "0.00")
        self.assertEqual(resposta.data["por_status"], dict.fromkeys(OrdemServico.Status.values, 0))

    def test_resumo_considera_filtros_e_todas_as_paginas(self):
        for _ in range(12):
            self.criar_ordem(valor_estimado="10.25")
        self.criar_ordem(status="concluida", valor_estimado="50.00")
        geral = self.client.get("/api/ordens/resumo/")
        self.assertEqual(geral.data["total"], 13)
        self.assertEqual(geral.data["valor_total_estimado"], "173.00")
        filtrado = self.client.get("/api/ordens/resumo/?status=aberta")
        self.assertEqual(filtrado.data["total"], 12)
        self.assertEqual(filtrado.data["por_status"]["concluida"], 0)
        self.assertEqual(filtrado.data["valor_total_estimado"], "123.00")
        self.assertNotIn("results", filtrado.data)


class ProtocoloTests(APIBase):
    def test_recurso_inexistente_em_todos_os_metodos(self):
        for recurso in ["clientes", "ordens"]:
            for metodo in ["get", "put", "patch", "delete"]:
                with self.subTest(recurso=recurso, metodo=metodo):
                    resposta = getattr(self.client, metodo)(f"/api/{recurso}/999999/")
                    self.assertEqual(resposta.status_code, 404)

    def test_json_malformado(self):
        resposta = self.client.post("/api/clientes/", '{"nome":', content_type="application/json")
        self.assertEqual(resposta.status_code, 400)

    def test_metodo_nao_permitido(self):
        self.assertEqual(self.client.post(f"/api/clientes/{self.ana.pk}/", {}).status_code, 405)

    @override_settings(DEBUG=False)
    def test_erro_inesperado_retorna_500_json_sem_vazar_detalhes(self):
        with patch("assistencia.views.ClienteViewSet.get_queryset", side_effect=RuntimeError("segredo-interno")):
            with self.assertLogs("assistencia.exceptions", level="ERROR"):
                resposta = self.client.get("/api/clientes/")
        self.assertEqual(resposta.status_code, 500)
        self.assertIn("application/json", resposta["Content-Type"])
        self.assertNotIn("segredo-interno", resposta.content.decode())
        self.assertIn("detail", resposta.data)

    def test_documentacao_e_raiz_disponiveis(self):
        for url in ["/api/", "/api/schema/", "/api/docs/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class PersistenciaTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome="Ana", email="ana@example.com", telefone="11999990001")

    def test_banco_rejeita_email_duplicado_sem_distinguir_caixa(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cliente.objects.create(nome="Outra", email="ANA@example.com", telefone="11999990002")

    def test_banco_rejeita_valor_status_e_prioridade_invalidos(self):
        for alteracao in [{"valor_estimado": "-1.00"}, {"status": "invalido"}, {"prioridade": "invalida"}]:
            with self.subTest(alteracao=alteracao):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    OrdemServico.objects.create(cliente=self.cliente, equipamento="PC", descricao="Teste", **alteracao)

    def test_seed_repetido_nao_duplica_nem_sobrescreve(self):
        call_command("seed_demo", stdout=StringIO())
        ordem = OrdemServico.objects.filter(cliente__email="ana.demo@example.com").first()
        ordem.status = "cancelada"
        ordem.save()
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Cliente.objects.count(), 4)
        self.assertEqual(OrdemServico.objects.count(), 12)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, "cancelada")
