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

## Book Search

As buscas públicas devem utilizar as mesmas regras de visibilidade do catálogo.

### Title

Status: IMPLEMENTED / NEEDS CATALOG ALIGNMENT

- substring;
- case-insensitive;
- trim nas extremidades;
- `%` e `_` tratados literalmente;
- somente obras visíveis no catálogo.

### Author

Status: APPROVED FOR IMPLEMENTATION

- substring;
- case-insensitive;
- trim nas extremidades;
- `%` e `_` tratados literalmente;
- somente obras visíveis no catálogo.

### ISBN

Status: PARTIALLY DEFINED

- busca sobre `books.isbn`;
- correspondência exata;
- somente obras visíveis no catálogo;
- normalização de hífens ainda precisa ser confirmada.

### Barcode

Status: APPROVED FOR IMPLEMENTATION

- busca sobre `copies.barcode`;
- correspondência exata;
- exemplar deve estar ativo;
- resultado deve levar à obra/exemplar correspondente.