# Feature — Busca de livros

## Rastreabilidade

| Issue | EAP | História | Prioridade | Tamanho | Status |
|---|---|---|---|---|---|
| #23 | 1.4.1 | Busca por título | P0 | XS | Implementada |
| #24 | 1.4.2 | Busca por autor | P0 | XS | Pendente |
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

Permitir que o usuário localize obras e exemplares do acervo através de diferentes critérios de busca:

- título;
- autor;
- ISBN;
- código de barras.

As três histórias pertencem ao mesmo domínio de consulta e devem reutilizar a mesma arquitetura de busca já implementada no backend.

---

## Arquitetura oficial da feature

As buscas públicas pertencem ao domínio de catálogo.

Controller:
`CatalogController`

Service:
`CatalogService`

Repository:
`CatalogRepository`

Models:
`Book`
`Copy`

A implementação de #23 em `book_*` é anterior à introdução do módulo
`catalog_*` e deve ser incorporada ao módulo de catálogo antes da
conclusão da feature.

# Issue #23 — Busca por título

## História

Como **funcionário responsável pelo acervo**,
quero **buscar obras por título**,
para **localizar rapidamente uma obra no acervo**.

## Situação

Implementada.

## Contrato aprovado

A busca por título:

- recebe um termo;
- aplica trim somente nas extremidades;
- rejeita termo vazio;
- utiliza correspondência parcial por substring;
- é case-insensitive;
- trata `%` e `_` como caracteres literais;
- retorna somente obras ativas;
- retorna coleção vazia quando não há correspondência;
- não altera dados.

## Endpoint atual

`GET /api/v1/books/?title=<termo>`

## Testes

Cobertura existente para:

- schema;
- repository;
- service;
- controller;
- substring;
- case-insensitive;
- filtro de obras ativas;
- `%` literal;
- `_` literal;
- validação do parâmetro;
- acesso público.

---

# Issue #24 — Busca por autor

## História

Como **funcionário responsável pelo acervo**,
quero **buscar obras por autor**,
para **localizar obras relacionadas ao autor informado**.

## Situação

Pendente.

## Escopo confirmado pela Story

A operação deve permitir localizar obras relacionadas ao autor informado.

## Decisões necessárias antes da implementação

### AUT-01 — Correspondência

Status: OPEN

Definir se a busca por autor será:

- exata;
- prefixo;
- substring.

### AUT-02 — Case sensitivity

Status: OPEN

Definir se:

`machado`

deve encontrar:

`Machado de Assis`

### AUT-03 — Obras inativas

Status: OPEN

Definir se obras inativas devem aparecer.

### AUT-04 — Normalização

Status: OPEN

Definir se será aplicado somente trim ou alguma normalização adicional.

## Reutilização esperada

A implementação deve reutilizar:

- `BookRepository`;
- `BookService`;
- `BookController`;
- schemas de busca existentes;
- infraestrutura de testes criada na #23.

Não criar novo módulo de busca apenas para autor.

---

# Issue #25 — Busca por ISBN ou código de barras

## História

Como **funcionário responsável pelo acervo**,
quero **buscar itens por ISBN ou código de barras**,
para **localizar rapidamente a obra ou exemplar a partir de um identificador**.

## Situação

Pendente.

## Observação importante de domínio

Esta Story envolve dois identificadores de entidades diferentes:

### ISBN

Pertence à obra:

`books.isbn`

### Código de barras

Pertence ao exemplar:

`copies.barcode`

Portanto, apesar de estarem na mesma Story, a implementação provavelmente exigirá consultas diferentes.

Não assumir que ISBN e barcode possuem a mesma semântica de busca.

## Decisões necessárias

### ID-01 — ISBN exato ou parcial

Status: OPEN

Definir se ISBN deve usar correspondência:

- exata;
- parcial.

### ID-02 — Normalização de ISBN

Status: OPEN

Definir tratamento de:

- hífens;
- espaços;
- ISBN-10;
- ISBN-13.

### ID-03 — Barcode exato ou parcial

Status: OPEN

Definir se código de barras exige correspondência exata.

### ID-04 — Exemplares inativos

Status: OPEN

Definir se exemplares com:

`is_active = false`

podem ser encontrados.

### ID-05 — Resultado

Status: OPEN

Definir se o endpoint:

- retorna obra para ISBN;
- retorna exemplar para barcode;
- utiliza schemas diferentes;
- utiliza um response discriminado.

## Banco já disponível

Não há evidência de necessidade de migration para a busca:

- `books.isbn` já existe;
- `copies.barcode` já existe.

A implementação deve primeiro tentar utilizar o schema atual.

---

# Critérios gerais de aceitação

Para cada modalidade implementada:

- [ ] entrada obrigatória validada;
- [ ] entrada inválida produz erro adequado;
- [ ] consulta não modifica dados;
- [ ] resultado é serializável pela API;
- [ ] nenhuma regra de negócio é inventada;
- [ ] repository contém a consulta;
- [ ] service coordena a operação;
- [ ] controller trata HTTP;
- [ ] testes automatizados cobrem o comportamento;
- [ ] testes existentes continuam passando.

---

# Fora do escopo da feature

Não implementar durante estas três histórias:

- cadastro de obras;
- atualização de obras;
- cadastro de exemplares;
- disponibilidade;
- venda;
- empréstimo;
- reserva;
- paginação genérica, salvo decisão posterior;
- motor de busca externo;
- Elasticsearch;
- ranking avançado;
- fuzzy search;
- busca full-text genérica.

---

# Definition of Done

A feature estará concluída quando:

## #23

- [x] busca por título implementada;
- [x] testes implementados.

## #24

- [ ] decisões de autor resolvidas;
- [ ] busca por autor implementada;
- [ ] testes implementados.

## #25

- [ ] decisões de ISBN/barcode resolvidas;
- [ ] busca por ISBN implementada;
- [ ] busca por barcode implementada;
- [ ] testes implementados.

## Feature

- [ ] todos os testes passando;
- [ ] diff revisado;
- [ ] nenhuma migration desnecessária;
- [ ] nenhuma alteração fora do escopo;
- [ ] PR da branch `feature/busca-livros` aprovada;
- [ ] integração com `integracao` concluída.