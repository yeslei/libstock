# Backend do LibStock

API REST construída com FastAPI seguindo MVC com camadas de serviço e repositório.

## Requisitos

- Python 3.12
- PostgreSQL 17 (Supabase local ou hospedado)

## Execução local

```bash
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```bash
pip install -r requirements.txt
```

Na raiz do repositório, inicie o PostgreSQL local do Supabase:

```bash
npm install
npx supabase start
```

Copie `.env.example` para `.env`, ajuste as variáveis e aplique todas as
migrations exclusivamente com Alembic:

```bash
alembic upgrade head
```

Como alternativa, execute `./start-backend.sh` na raiz do projeto. O script
instala as dependências, aplica as migrations pendentes e só então inicia a API.

Inicie a API:

```bash
uvicorn app.main:app --reload
```

A documentação interativa estará em `http://localhost:8000/docs`.

## Endpoints iniciais

| Método | Endpoint | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/health` | Não | Verifica a disponibilidade da API |
| `POST` | `/api/v1/auth/register` | Não | Cadastra uma conta PF ou PJ |
| `POST` | `/api/v1/auth/login` | Não | Autentica e cria uma sessão |
| `POST` | `/api/v1/auth/refresh` | Cookie | Rotaciona o refresh token |
| `POST` | `/api/v1/auth/logout` | Cookie | Revoga a sessão atual |
| `POST` | `/api/v1/auth/logout-all` | Bearer | Revoga todas as sessões do usuário |
| `GET` | `/api/v1/users/me` | Bearer | Retorna o usuário autenticado |
| `GET` | `/api/v1/users` | Bearer (`ADMINISTRATOR`) | Lista usuários e permite filtro por papel |
| `GET` | `/api/v1/users/{id}` | Bearer (`ADMINISTRATOR`) | Consulta um usuário para gestão |
| `PATCH` | `/api/v1/users/{id}` | Bearer (`ADMINISTRATOR`) | Atualiza nome, e-mail e papel funcional |
| `PATCH` | `/api/v1/users/{id}/inactivate` | Bearer (`ADMINISTRATOR`) | Inativa o usuário e revoga suas sessões |
| `POST` | `/api/v1/employees/` | Bearer (`ADMINISTRATOR`) | Cadastra vendedor, estoquista ou administrador |
| `POST` | `/api/v1/books/` | Bearer (`STOCK_KEEPER`, `ADMINISTRATOR`) | Cadastra uma obra e seu exemplar inicial ativo na mesma transação |

## Permissionamento

O backend usa RBAC com `roles` e `user_roles`. Os códigos técnicos oficiais são
`USER`, `SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR`; o campo `name` pode mudar
sem quebrar regras do sistema. Cadastros públicos recebem `USER`
automaticamente.

Rotas futuras podem reutilizar a dependency `require_roles(...)`:

```python
Depends(require_roles("SELLER", "ADMINISTRATOR"))
```

## Variáveis de ambiente

Consulte `.env.example`. Segredos e URLs reais não devem ser versionados.

## Banco de dados

O Supabase é usado como provedor PostgreSQL. O FastAPI acessa o banco por
SQLAlchemy/psycopg e é a única API consumida pelo frontend. A CLI instalada na
raiz serve apenas para executar o ambiente local; ela não é uma dependência do
backend e não gerencia o esquema. Toda alteração estrutural deve ser criada em
`backend/migrations` com Alembic.
# Gestão operacional do acervo

- `GET /api/v1/books/?title=...`: busca pública legada por título.
- `GET /api/v1/books/{book_id}`: detalhes internos da obra e seus exemplares (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `PATCH /api/v1/books/{book_id}`: altera metadados e link da capa (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `POST /api/v1/books/`: cria obra com primeiro exemplar (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `POST /api/v1/copies/`: adiciona exemplar à obra (`STOCK_KEEPER`, `ADMINISTRATOR`).
