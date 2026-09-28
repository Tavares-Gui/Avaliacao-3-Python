"""Interface HTML: recebe formulários e consome a API via HTTP, sem JavaScript."""
import json
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

CAMPOS = {
    "clientes": ("nome", "email", "telefone"),
    "ordens": ("cliente_id", "equipamento", "descricao", "status", "prioridade", "valor_estimado"),
}
STATUS = (("aberta", "Aberta"), ("em_andamento", "Em andamento"), ("concluida", "Concluída"), ("cancelada", "Cancelada"))
PRIORIDADES = (("baixa", "Baixa"), ("normal", "Normal"), ("alta", "Alta"))


def chamar_api(request, caminho, metodo="GET", dados=None):
    """Chama somente rotas internas construídas pelo painel, no mesmo host/porta."""
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    requisicao = Request(
        request.build_absolute_uri(caminho), data=corpo, method=metodo,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    resultado = {"metodo": metodo, "caminho": caminho}
    try:
        # Localhost não depende de proxies eventualmente configurados na máquina.
        cliente_http = build_opener(ProxyHandler({}))
        try:
            resposta = cliente_http.open(requisicao, timeout=5)
        except HTTPError as erro:
            resposta = erro  # 400/404 também têm corpo útil, com os erros da API.
        with resposta:
            status = resposta.status
            conteudo = resposta.read().decode("utf-8")
        try:
            retorno = json.loads(conteudo) if conteudo else None
        except json.JSONDecodeError:
            retorno = {"detail": "O servidor retornou uma resposta que não é JSON."}
        resultado.update(
            status=status, ok=200 <= status < 300,
            motivo=HTTPStatus(status).phrase, dados=retorno,
            json=json.dumps(retorno, ensure_ascii=False, indent=2) if retorno is not None else "",
        )
    except (URLError, TimeoutError, OSError):
        # Não inventamos um status HTTP quando nenhuma resposta chegou.
        resultado.update(status=None, ok=False, motivo="Sem conexão", dados=None, json="")
    return resultado


def opcoes_clientes(request):
    """Percorre a paginação para o seletor incluir clientes além da primeira página."""
    clientes = []
    pagina = 1
    while True:
        resposta = chamar_api(request, f"/api/clientes/?page={pagina}")
        if not resposta["ok"]:
            return clientes, "Não foi possível carregar todos os clientes. Tente novamente."
        clientes.extend(resposta["dados"]["results"])
        if not resposta["dados"]["next"]:
            return clientes, ""
        pagina += 1


@require_http_methods(["GET", "POST"])
def painel(request):
    recurso = request.POST.get("recurso") if request.method == "POST" else request.GET.get("recurso", "ordens")
    if recurso not in CAMPOS:
        recurso = "ordens"
    identificador = request.POST.get("id", "") if request.method == "POST" else request.GET.get("id", "")
    if identificador and (not identificador.isascii() or not identificador.isdecimal()):
        identificador = "0"  # Consulta inválida resulta em 404, sem aceitar caminhos arbitrários.

    if request.method == "POST":
        acao = request.POST.get("acao")
        dados = {campo: request.POST.get(campo, "") for campo in CAMPOS[recurso]}
        caminho = f"/api/{recurso}/"
        if acao == "criar":
            resultado = chamar_api(request, caminho, "POST", dados)
        elif acao in {"editar", "parcial", "excluir"} and identificador:
            caminho += f"{identificador}/"
            if acao == "excluir":
                resultado = chamar_api(request, caminho, "DELETE")
            elif acao == "parcial":
                campo = "telefone" if recurso == "clientes" else "status"
                resultado = chamar_api(request, caminho, "PATCH", {campo: dados[campo]})
            else:
                resultado = chamar_api(request, caminho, "PUT", dados)
        else:
            return redirect(f"/?recurso={recurso}")

        resultado["titulo"] = {
            "criar": "Cadastro realizado." if resultado["ok"] else "Não foi possível cadastrar.",
            "editar": "Alterações salvas." if resultado["ok"] else "Não foi possível salvar.",
            "parcial": "Campo atualizado." if resultado["ok"] else "Não foi possível atualizar.",
            "excluir": "Registro excluído." if resultado["ok"] else "Não foi possível excluir.",
        }[acao]
        request.session["painel_resultado"] = resultado
        # Preserva entradas inválidas para a pessoa poder corrigi-las.
        if not resultado["ok"] and acao in {"criar", "editar"}:
            request.session["painel_formulario"] = dados
        query = {"recurso": recurso}
        if identificador and (acao != "excluir" or not resultado["ok"]):
            query["id"] = identificador
        # POST/Redirect/GET: atualizar a página não repete um cadastro/exclusão.
        return redirect("/?" + urlencode(query) + "#resultado")

    parametros = {chave: request.GET[chave] for chave in ("search", "ordering", "page") if request.GET.get(chave)}
    if recurso == "ordens":
        parametros.update({chave: request.GET[chave] for chave in ("status", "prioridade") if request.GET.get(chave)})
    caminho_lista = f"/api/{recurso}/"
    if parametros:
        caminho_lista += "?" + urlencode(parametros)
    lista = chamar_api(request, caminho_lista)
    resultado = request.session.pop("painel_resultado", None)
    formulario_salvo = request.session.pop("painel_formulario", None)
    resumo = chamar_api(request, "/api/ordens/resumo/")
    avisos = []
    formulario = {"status": "aberta", "prioridade": "normal", "valor_estimado": "0.00"}
    selecionado = None
    if identificador:
        detalhe = chamar_api(request, f"/api/{recurso}/{identificador}/")
        if detalhe["ok"]:
            selecionado = detalhe["dados"]
            formulario = dict(selecionado)
            if recurso == "ordens":
                formulario["cliente_id"] = str(selecionado["cliente"]["id"])
        resultado = resultado or detalhe
    if formulario_salvo is not None:
        formulario = formulario_salvo

    clientes = []
    if recurso == "ordens":
        clientes, aviso = opcoes_clientes(request)
        if aviso:
            avisos.append(aviso)
    if not resumo["ok"]:
        avisos.append("O resumo não está disponível no momento.")
    if not lista["ok"]:
        avisos.append("Não foi possível carregar a listagem. Confira a resposta da API.")
    resultado = resultado or lista
    if not resultado.get("titulo"):
        resultado["titulo"] = "Consulta realizada." if resultado["ok"] else "Não foi possível consultar."
    mensagens = []
    erros = {}
    if not resultado["ok"]:
        if resultado["status"] is None:
            mensagens = ["A API não respondeu. Verifique se o servidor está disponível e tente novamente."]
        elif isinstance(resultado["dados"], dict):
            erros = resultado["dados"]
            for campo, valor in erros.items():
                texto = "; ".join(str(item) for item in valor) if isinstance(valor, list) else str(valor)
                mensagens.append(texto if campo == "detail" else f"{campo}: {texto}")
    paginacao = lista["dados"] if lista["ok"] else {"results": [], "count": 0}
    numero_pagina = int(parametros.get("page", "1")) if parametros.get("page", "1").isdigit() else 1

    def link_pagina(numero):
        return "/?" + urlencode({"recurso": recurso, **parametros, "page": numero})

    return render(request, "assistencia/painel.html", {
        "recurso": recurso, "eh_ordem": recurso == "ordens",
        "registros": paginacao.get("results", []), "total": paginacao.get("count", 0),
        "pagina": numero_pagina,
        "anterior": link_pagina(numero_pagina - 1) if paginacao.get("previous") else "",
        "proxima": link_pagina(numero_pagina + 1) if paginacao.get("next") else "",
        "filtros": parametros, "resumo": resumo["dados"] if resumo["ok"] else None,
        "clientes": clientes, "formulario": formulario, "selecionado": selecionado,
        "confirmar_exclusao": request.GET.get("excluir") == "1" and selecionado is not None,
        "resultado": resultado, "mensagens": mensagens, "erros": erros, "avisos": avisos,
        "status_opcoes": STATUS, "prioridades": PRIORIDADES,
    })

