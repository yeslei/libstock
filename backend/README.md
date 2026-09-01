# Backend do LibStock

API REST construída com FastAPI seguindo MVC com camadas de serviço e repositório.

## Requisitos

- Python 3.12
- PostgreSQL no Supabase para produção

## Execução local

```bash
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env`, ajuste as variáveis e aplique as migrations:

```bash
alembic upgrade head
```

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

## Variáveis de ambiente

Consulte `.env.example`. Segredos e URLs reais não devem ser versionados.
