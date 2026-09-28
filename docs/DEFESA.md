# Guia de defesa — Assistência Técnica API

## Explicação de abertura

“Nosso sistema gerencia uma assistência técnica. Temos clientes e ordens de serviço em uma relação um para muitos. O Django ORM cuida da persistência no SQLite; o Django REST Framework oferece a API. Usamos ModelSerializer para converter e validar dados e ModelViewSet com DefaultRouter para os endpoints. Acrescentamos documentação, filtros, um resumo gerencial e testes.”

Procure compreender esse caminho no código, em vez de decorar palavras.

## Caminho de uma requisição

```text
Cliente HTTP
  -> config/urls.py
  -> assistencia/urls.py (DefaultRouter)
  -> ViewSet (ação correspondente ao método)
  -> Serializer (validação/representação)
  -> Model e ORM
  -> SQLite
  -> Serializer -> Response JSON + status HTTP
```

Na criação: o DRF chama `serializer.is_valid()`, salva o objeto e responde `201`. Na listagem, consulta os objetos, filtra, pagina e serializa. Não há SQL escrito manualmente.

## Demonstração sugerida — 10 a 15 minutos

1. Mostre os models: duas tabelas de negócio, a chave estrangeira e `PROTECT`.
2. Execute `python manage.py showmigrations` no ambiente virtual e explique por que versionamos as migrações.
3. Inicie o servidor e abra `/api/` ou `/api/docs/`.
4. Faça POST de cliente. Aponte o `201` e seu ID.
5. Faça GET da lista e do detalhe de cliente: `200`.
6. Faça PUT completo de cliente, depois PATCH só do telefone. Mostre que PUT incompleto dá `400`.
7. Faça POST de ordem usando o ID do cliente. Mostre a resposta com cliente aninhado.
8. Mostre a lista de ordens e o detalhe do cliente agora com a ordem resumida.
9. Faça PUT completo e PATCH de status na ordem. Explique os campos obrigatórios e os campos somente de leitura.
10. Mostre paginação (seed tem 12 ordens), filtros combinados, busca e ordenação.
11. Mostre `/api/ordens/resumo/` e depois `?status=aberta`.
12. Tente valor negativo, e-mail inválido e cliente inexistente no corpo: `400`.
13. Tente apagar o cliente vinculado: `400`. Mostre que ambos os registros continuam existindo.
14. Apague a ordem e depois o cliente: `204`, sem corpo. Consulte o ID removido: `404`.
15. Rode os testes e explique que o caso `500` usa uma falha simulada.

A coleção Postman já possui essa sequência e confere os códigos. Um erro na sequência pode deixar dados de demonstração; eles podem ser removidos pela API. O e-mail da coleção usa um GUID por execução para evitar conflito com execuções anteriores.

## Demonstração pelo painel, sem Swagger

Abra http://127.0.0.1:8000/ com o servidor rodando. A interface usa apenas HTML e CSS; o Django envia as chamadas HTTP à API.

1. Entre em **Clientes**, preencha o formulário e cadastre. Mostre **201 Created** e expanda **Ver resposta da API** para ver o ID.
2. Clique em **Abrir** na linha do cliente. Mostre o **GET 200** e o detalhe.
3. Edite o nome e use **Salvar alterações**: **PUT 200**.
4. Expanda **Alterar apenas o telefone**, informe outro telefone e atualize: **PATCH 200**.
5. Entre em **Ordens de serviço**, escolha o cliente e cadastre uma ordem: **POST 201**.
6. Abra a ordem. Mostre **Cliente vinculado** e o JSON aninhado.
7. Salve o formulário completo: **PUT 200**. Depois expanda **Alterar apenas o status**: **PATCH 200**.
8. Use filtros, busca, ordenação e **Próxima** para demonstrar a listagem.
9. Abra a ordem, coloque um valor negativo e salve: **400 Bad Request**, com mensagem ao lado do campo. Corrija depois.
10. No cadastro de cliente, use um e-mail inválido: **400**. Os dados digitados permanecem para correção.
11. Abra um cliente com ordens e clique em **Excluir cliente**, depois **Confirmar exclusão**: **400**, pela proteção do relacionamento.
12. Exclua a ordem criada na apresentação: **204 No Content**, sem corpo. Depois exclua seu cliente: **204**.
13. Em **Consultar pelo ID**, informe um dos IDs excluídos: **404 Not Found**.

O resumo superior é geral e não muda de escopo quando a tabela é filtrada. Ele mostra estimativas, não faturamento.

Explique a diferença entre as duas requisições: o navegador envia o formulário ao painel; a view Python chama a API com o método adequado. O painel exibe o status desta chamada à API. Não há simulação de sucesso/erro.

Para demonstrar 500, continue usando o teste automatizado de falha simulada. Não é necessário nem desejável manter uma operação propositalmente quebrada na interface.

## Perguntas prováveis

### Por que esse relacionamento é 1:N?

A coluna `cliente_id` fica na tabela da ordem. Várias ordens podem apontar para o mesmo cliente. Uma única ordem não pode apontar para vários clientes. `related_name="ordens"` permite consultar o sentido inverso com `cliente.ordens.all()`.

### O que é ORM? E uma migração?

ORM mapeia classes/objetos para tabelas/registros e produz consultas SQL. Migração é uma versão da estrutura do banco. `makemigrations` gera o arquivo de alteração; `migrate` aplica alterações pendentes. Não se deve apagar migrações para “resolver” divergências em um projeto compartilhado.

### Por que SQLite?

O enunciado permite SQLite. É relacional, persiste em arquivo e dispensa serviço externo. O acesso usa o ORM, mas trocar de banco não significa que todas as características e limitações sejam idênticas. Ele atende ao tamanho e à demonstração deste projeto.

### Qual a função de ModelSerializer?

Deriva campos e parte das validações do model, converte os objetos em dados que o renderer transforma em JSON e valida o JSON de entrada antes de criar/atualizar objetos. Validações específicas, como e-mail sem distinguir caixa, foram adicionadas explicitamente.

### Como o relacionamento é enviado e recebido?

O POST/PUT recebe `cliente_id`. `PrimaryKeyRelatedField` procura o cliente e rejeita uma chave inexistente. `source="cliente"` direciona o valor para a relação do model. Na saída, `cliente` usa `ClienteResumoSerializer`. Assim não é necessário reenviar nome, e-mail e telefone para criar uma ordem.

### Como evitamos ciclos?

O detalhe do cliente contém apenas resumos das ordens. O resumo da ordem não contém cliente. O cliente aninhado em uma ordem também não contém a lista de ordens. A árvore de dados termina.

### PUT e PATCH são iguais?

Não. PUT substitui os campos editáveis e exige todos eles; PATCH recebe somente o que será alterado. O DRF usa `partial=True` na atualização parcial. Exigimos status, prioridade e valor no serializer mesmo que o model tenha defaults. ID e datas são controlados pelo servidor e não entram nessa substituição.

### Por que PROTECT em vez de CASCADE?

Queremos impedir a perda acidental das ordens ao apagar um cliente. Com CASCADE, as ordens seriam apagadas junto. PROTECT levanta `ProtectedError`, convertido em `400` com uma mensagem. Excluir primeiro as ordens ou transferi-las libera a exclusão do cliente.

### Por que usar DecimalField?

Valores monetários precisam de representação decimal com casas definidas. `float` usa representação binária que pode introduzir aproximações. O DRF representa o valor decimal como string no JSON. Usamos no máximo oito dígitos inteiros e duas casas decimais.

### Quais validações existem?

Obrigatoriedade, tamanho e tipo dos campos; formato e unicidade do e-mail; telefone numérico de 10/11 dígitos; existência do cliente; choices de status/prioridade; precisão e não negatividade do valor. Algumas regras também possuem constraints no banco. `Model.save()` sozinho não chama `full_clean()`: por isso não podemos afirmar que toda validação do serializer também será aplicada automaticamente em qualquer escrita ORM.

### Como os códigos HTTP são escolhidos?

O ModelViewSet já implementa 200, 201 e 204 conforme a ação. ValidationError/serializers geram 400 e busca de recurso ausente gera 404. Nosso handler trata exclusão protegida e falhas inesperadas. Um erro inesperado nunca deve virar um falso 200.

### Por que não existe endpoint para gerar erro 500?

500 representa uma falha imprevista, não uma operação de negócio. O teste usa `unittest.mock.patch` para fazer uma consulta falhar e verificar resposta e registro de log sem manter uma rota defeituosa na API.

### O que o DefaultRouter faz?

Registra cada ViewSet e gera as rotas de coleção e detalhe, relacionando GET/POST/PUT/PATCH/DELETE com suas ações. `@action(detail=False)` acrescenta `/api/ordens/resumo/`, que opera sobre a coleção inteira.

### O resumo respeita paginação?

Respeita os filtros e busca, mas calcula sobre todos os resultados filtrados. Usa `Count` e `Sum` no banco. Retorna todos os status com zero quando não há ocorrências. A soma é de orçamentos, inclusive os de ordens canceladas se não houver filtro; não é receita.

### O que são select_related e prefetch_related?

`select_related("cliente")` busca a ordem e seu cliente com JOIN, evitando uma consulta adicional para cada ordem listada. `prefetch_related("ordens")` busca as ordens relacionadas ao detalhe de cliente em uma consulta separada. São otimizações; não alteram o formato da resposta.

### O que fica no .env?

SECRET_KEY, DEBUG, hosts permitidos e localização do banco. A chave é gerada localmente. SQLite não possui usuário/senha próprios. O `.env.example` tem apenas orientações e valores não secretos. A chave real, banco e ambiente virtual ficam fora do Git.

### Como explicamos os testes?

Cada teste prepara dados, faz uma requisição HTTP pelo cliente de testes do DRF e verifica resposta e, quando necessário, estado do banco. O banco de testes é descartável. Há casos de sucesso e falha para não verificar apenas o caminho feliz.

### Há autenticação na API?

Não: o escopo é demonstração acadêmica local, com `AllowAny`. O painel admin exige login. Autenticação de consumidores e permissões seriam uma evolução separada, não um requisito resolvido pelo .env.

## Divisão de estudo

Todos devem conhecer o fluxo completo. Para organizar uma primeira leitura, uma pessoa pode apresentar models/migrações, outra serializers/validações e outra views/rotas/testes. Depois troquem os papéis: a avaliação é individual e ninguém deve ficar limitado a um único arquivo.

## Limites assumidos do projeto

- Há um painel simples em HTML e CSS servido pelo Django, além do DRF e Swagger.
- Não há login na API pública nem autorização por cliente.
- Não há histórico de movimentação, pagamento ou transição obrigatória de status.
- O detalhe de cliente aninha todas as ordens; o crescimento dessa lista exigiria mudar a representação.
- Busca e ordenação seguem os comportamentos padrões documentados do DRF.
- Não há deploy de produção configurado.
- O workflow só roda remotamente depois de enviar o código ao GitHub.

Esses limites mantêm a atividade focada nos requisitos de Django/DRF e deixam explícito o que cada integrante realmente precisa explicar.
