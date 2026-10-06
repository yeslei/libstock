# LibStock

Sistema de gestão de acervos de livros para pessoas físicas e jurídicas.

O LibStock permitirá cadastrar e administrar obras e exemplares físicos, consultar disponibilidade e controlar diferentes modalidades de circulação, como venda, troca e empréstimo.

## Tecnologias planejadas

- Backend: Python e FastAPI
- Frontend: Angular
- Banco de dados: PostgreSQL no Supabase, acessado pelo FastAPI via SQLAlchemy
- Backend em produção: Render
- Frontend em produção: Vercel

## Estrutura

```text
libstock/
├── backend/    # API FastAPI
└── frontend/   # Aplicação Angular (a iniciar)
```

## Backend

O primeiro incremento implementa autenticação própria com JWT de acesso, refresh token rotativo e persistência das sessões no PostgreSQL.

O FastAPI é a única porta de entrada para dados e regras de negócio. A CLI do
Supabase na raiz é utilizada somente para o PostgreSQL local; o esquema é
versionado exclusivamente pelas migrations Alembic do backend.

Consulte as instruções em [`backend/README.md`](backend/README.md).

## Status

Backend de autenticação em desenvolvimento. Frontend ainda não iniciado.
