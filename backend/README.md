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
| `POST` | `/api/v1/books/` | Bearer (`STOCK_KEEPER`, `MANAGER`, `ADMINISTRATOR`) | Cadastra uma obra e seu exemplar inicial ativo na mesma transação |

## Permissionamento

O backend usa RBAC com `roles` e `user_roles`. Os códigos técnicos iniciais são
`USER`, `SELLER` e `MANAGER`; o campo `name` pode mudar sem quebrar regras do
sistema. Cadastros públicos recebem `USER` automaticamente.

Rotas futuras podem reutilizar a dependency `require_roles(...)`:

```python
Depends(require_roles("SELLER", "MANAGER"))
```

## Variáveis de ambiente

Consulte `.env.example`. Segredos e URLs reais não devem ser versionados.

## Banco de dados

O Supabase é usado como provedor PostgreSQL. O FastAPI acessa o banco por
SQLAlchemy/psycopg e é a única API consumida pelo frontend. A CLI instalada na
raiz serve apenas para executar o ambiente local; ela não é uma dependência do
backend e não gerencia o esquema. Toda alteração estrutural deve ser criada em
`backend/migrations` com Alembic.
