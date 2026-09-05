# Feature — Busca de livros

## Rastreabilidade

| Issue | EAP | História | Prioridade | Tamanho | Status |
|---|---|---|---|---|---|
| #23 | 1.4.1 | Busca por título | P0 | XS | Implementada |
| #24 | 1.4.2 | Busca por autor | P0 | XS | Implementada |
| #25 | 1.4.3 | Busca por ISBN ou código de barras | P0 | S | Pendente |

Branch:

`feature/busca-livros`

Milestone:

`V1`

Pacote principal:

`Consulta do Acervo`

Dependência EAP comum:

`1.3.1`

---

# Objetivo da feature

Permitir que o usuário localize obras e exemplares do acervo por:

- título;
- autor;
- ISBN;
- código de barras.

As histórias pertencem ao domínio de consulta do acervo e devem reutilizar a arquitetura pública de catálogo.

---

# Arquitetura oficial da feature

As buscas públicas pertencem ao domínio de catálogo.

Fluxo:

`CatalogController`
→ `CatalogService`
→ `CatalogRepository`
→ SQLAlchemy
→ PostgreSQL

Models principais:

- `Book`
- `Copy`

Arquivos principais:

- `backend/app/controllers/catalog_controller.py`
- `backend/app/services/catalog_service.py`
- `backend/app/repositories/catalog_repository.py`
- `backend/app/schemas/catalog_schema.py`
- `backend/app/models/domain.py`

A implementação inicial da #23 em `book_*` foi criada antes da introdução do módulo `catalog_*`.

Título e autor foram consolidados no catálogo público.

A rota legada `/api/v1/books/` permanece temporariamente disponível para evitar quebra de consumidores e testes existentes, mas novas buscas devem evoluir o módulo `catalog_*`.

---

# Regras gerais do catálogo público

As consultas públicas:

- não exigem autenticação;
- retornam somente obras ativas;
- retornam somente obras que possuam ao menos um exemplar ativo;
- não alteram dados;
- utilizam a mesma regra-base de visibilidade do catálogo.

Uma obra pode continuar visível mesmo quando nenhum exemplar está disponível, desde que exista ao menos um exemplar ativo.

---

# Issue #23 — Busca por título

## História

Como **funcionário responsável pelo acervo**,
quero **buscar obras por título**,
para **localizar rapidamente uma obra no acervo**.

## Situação

Implementada e consolidada no catálogo público.

## Contrato aprovado

A busca por título:

- recebe um termo;
- aplica trim somente nas extremidades;
- rejeita termo vazio;
- utiliza correspondência parcial por substring;
- é case-insensitive;
- trata `%` e `_` como caracteres literais;
- utiliza as regras de visibilidade do catálogo;
- retorna coleção vazia quando não há correspondência;
- não altera dados.

## Endpoint principal

`GET /api/v1/catalog/books?title=<termo>`

## Endpoint legado

`GET /api/v1/books/?title=<termo>`

Mantido temporariamente por compatibilidade.

## Testes

Cobertura para:

- validação;
- acesso público;
- substring;
- case-insensitive;
- escaping de `%`;
- escaping de `_`;
- visibilidade do catálogo;
- serialização da resposta.

---

# Issue #24 — Busca por autor

## História

Como **funcionário responsável pelo acervo**,
quero **buscar obras por autor**,
para **localizar obras relacionadas ao autor informado**.

## Situação

Implementada.

## Decisões aprovadas

### AUT-01 — Correspondência

Status: APPROVED

Busca por substring.

Exemplo:

`Assis`

pode encontrar:

`Machado de Assis`

### AUT-02 — Case sensitivity

Status: APPROVED

A busca é case-insensitive.

Exemplo:

`machado`

encontra:

`Machado de Assis`

### AUT-03 — Obras inativas

Status: APPROVED

A busca segue a regra de visibilidade do catálogo:

- `Book.is_active = true`;
- deve existir ao menos um `Copy.is_active = true`.

### AUT-04 — Normalização

Status: APPROVED

Aplicar trim somente nas extremidades.

`%` e `_` devem ser tratados como caracteres literais na busca.

## Endpoint

`GET /api/v1/catalog/books?author=<termo>`

## Testes

Cobertura adicionada para:

- busca por autor;
- acesso público;
- validação de ausência de critérios;
- integração com o catálogo.

---

# Contrato do endpoint de busca

Endpoint:

`GET /api/v1/catalog/books`

Critérios atualmente suportados:

- `title`
- `author`

Exemplos:

`GET /api/v1/catalog/books?title=dom`

`GET /api/v1/catalog/books?author=machado`

Ao menos um critério deve ser informado.

Entrada sem título e sem autor:

`GET /api/v1/catalog/books`

deve resultar em erro HTTP de validação.

---

# Issue #25 — Busca por ISBN ou código de barras

## História

Como **funcionário responsável pelo acervo**,
quero **buscar itens por ISBN ou código de barras**,
para **localizar rapidamente a obra ou exemplar a partir de um identificador**.

## Situação

Pendente.

## Observação de domínio

A Story envolve identificadores pertencentes a entidades diferentes.

### ISBN

Pertence à obra:

`books.isbn`

### Código de barras

Pertence ao exemplar:

`copies.barcode`

A implementação deve permanecer no domínio de catálogo, mas pode exigir consultas diferentes no `CatalogRepository`.

Não criar outro módulo de busca apenas para a #25.

---

# Decisões pendentes da #25
### ID-01 — Correspondência de ISBN

Status: APPROVED

- correspondência exata.

### ID-02 — Normalização de ISBN

Status: APPROVED

- trim somente nas extremidades;
- não remover hífens;
- não remover espaços internos;
- não converter ISBN-10/ISBN-13;
- não validar checksum na V1.

### ID-03 — Código de barras

Status: APPROVED

- correspondência exata.

### ID-04 — Exemplares inativos

Status: APPROVED

- `Copy.is_active = true`.

### ID-05 — Resultado

Status: APPROVED

- ISBN retorna `CatalogBookResponse`;
- barcode também retorna `CatalogBookResponse` da obra associada;
- não criar schema específico de exemplar nesta Story.
---

# Banco disponível

Não há necessidade identificada de nova migration para a #25.

Campos existentes:

- `books.isbn`;
- `copies.barcode`.

A implementação deve utilizar o schema atual, salvo descoberta concreta em contrário.

---

# Critérios gerais de aceitação

Para cada modalidade implementada:

- [x] entrada obrigatória validada;
- [x] entrada inválida produz erro HTTP adequado;
- [x] consulta não modifica dados;
- [x] resultado é serializável pela API;
- [x] repository contém a consulta;
- [x] service coordena a operação;
- [x] controller trata HTTP;
- [x] testes automatizados cobrem o comportamento;
- [x] testes existentes continuam passando.

Esses itens estão atendidos para #23 e #24.

Para #25, devem ser reavaliados após a implementação.

---

# Fora do escopo

Não implementar nesta feature:

- cadastro de obras;
- atualização de obras;
- cadastro de exemplares;
- empréstimos;
- vendas;
- reservas;
- motor de busca externo;
- Elasticsearch;
- fuzzy search;
- ranking avançado;
- busca full-text genérica;
- refatorações amplas não necessárias à busca.

---

# Validação atual

Última suíte completa executada:

`33 passed, 1 warning`

Comando:

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m pytest -q