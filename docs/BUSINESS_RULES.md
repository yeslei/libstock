# Business Rules

## Public Catalog

- O catálogo é navegável sem autenticação.
- Operações transacionais permanecem protegidas.
- Consultas públicas utilizam `/api/v1/catalog`.

### Visibilidade de obras

Uma obra aparece no catálogo quando:

- `books.is_active = true`;
- existe pelo menos um exemplar com `copies.is_active = true`.

A obra não é removida do catálogo apenas por estar sem exemplar disponível.

Quando existe exemplar ativo, mas nenhum está disponível, a obra permanece visível com sinalização de indisponibilidade.

---

## Book Search

As buscas públicas utilizam as mesmas regras de visibilidade do catálogo.

### Title

Status: IMPLEMENTED

- busca sobre `books.title`;
- correspondência por substring;
- case-insensitive;
- trim somente nas extremidades;
- entrada vazia após trim é inválida;
- `%` e `_` são tratados literalmente;
- somente obras visíveis no catálogo;
- ausência de correspondência retorna coleção vazia.

Endpoint:

`GET /api/v1/catalog/books?title=<termo>`

### Author

Status: IMPLEMENTED

- busca sobre `books.author`;
- correspondência por substring;
- case-insensitive;
- trim somente nas extremidades;
- entrada vazia após trim é inválida;
- `%` e `_` são tratados literalmente;
- somente obras visíveis no catálogo;
- ausência de correspondência retorna coleção vazia.

Endpoint:

`GET /api/v1/catalog/books?author=<termo>`

### Search validation

Atualmente a busca do catálogo exige pelo menos um critério válido.

Critérios implementados:

- `title`;
- `author`.

Requisição sem critério válido deve produzir erro HTTP de validação.

---

### ISBN

Status: APPROVED FOR IMPLEMENTATION

- busca sobre `books.isbn`;
- correspondência exata;
- aplicar somente trim nas extremidades;
- não remover hífens;
- não remover espaços internos;
- não converter automaticamente entre ISBN-10 e ISBN-13;
- não validar checksum na V1;
- comparar com o valor armazenado no banco;
- somente obras visíveis no catálogo;
- ausência de correspondência retorna coleção vazia;
- não exige migration.

Decisão:

Na V1, o ISBN deve ser informado no mesmo formato em que está armazenado no banco.

Exemplo:

`978-85-1234-567-8`

não é automaticamente tratado como equivalente a:

`9788512345678`

Normalização adicional de ISBN fica fora do escopo desta versão.
### Barcode

Status: APPROVED FOR IMPLEMENTATION

- busca sobre `copies.barcode`;
- correspondência exata;
- aplicar somente trim nas extremidades;
- exemplar deve possuir `copies.is_active = true`;
- a obra relacionada também deve respeitar as regras de visibilidade do catálogo;
- ausência de correspondência retorna coleção vazia;
- não exige migration.

Resultado:

A busca por código de barras retorna a obra correspondente usando `CatalogBookResponse`.

Não será criado um schema específico de exemplar para esta Story.

O código de barras funciona como identificador de localização do exemplar, mas o resultado público da busca permanece no nível de obra.

## Decisions

### ISBN normalization

Status: APPROVED

- trim nas extremidades;
- sem normalização de hífens/espaços;
- sem conversão ISBN-10/ISBN-13;
- sem checksum na V1.

### Barcode response

Status: APPROVED

- retorna `CatalogBookResponse` da obra associada ao exemplar;
- não retorna schema específico de `Copy` nesta versão.