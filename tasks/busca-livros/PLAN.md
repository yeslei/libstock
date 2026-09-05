# Plan — Busca de livros

## 1. Consolidar #23 no catálogo

- mover/reutilizar busca por título no CatalogRepository;
- usar regra-base `_catalog_books()`;
- expor via CatalogService;
- expor via CatalogController;
- preservar comportamento e testes;
- remover `book_*` somente depois da equivalência.

## 2. #24 — Autor

Reutilizar a mesma infraestrutura de busca do título:

- substring;
- case-insensitive;
- trim;
- escaping de LIKE;
- regras de visibilidade do catálogo.

## 3. #25 — ISBN / Barcode

### ISBN
- consulta exata em Book.isbn.

### Barcode
- consulta exata em Copy.barcode;
- somente exemplar ativo.

## Verificação

cd backend
PYTHONPATH=. .venv/bin/python -m pytest -q