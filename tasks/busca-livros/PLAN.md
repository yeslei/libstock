# Plan — Busca de livros

## Concluído

### #23 — Título

Implementado usando:

- BookRepository
- BookService
- BookController
- schemas
- testes

Não reimplementar nem redesenhar esse fluxo.

---

## Próximo — #24 Autor

Após resolver AUT-01 até AUT-04:

1. estender schema/query params;
2. adicionar busca no BookRepository;
3. reutilizar BookService;
4. expor no controller;
5. adicionar testes;
6. rodar suíte completa.

---

## Depois — #25 ISBN / Barcode

Após resolver ID-01 até ID-05:

1. reutilizar BookRepository para ISBN;
2. verificar repository/model de Copy para barcode;
3. implementar consultas sem migration;
4. integrar service/controller;
5. definir response conforme decisão aprovada;
6. adicionar testes;
7. rodar suíte completa.

---

## Verificação

A partir de `backend/`:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q