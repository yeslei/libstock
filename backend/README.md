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

### V2: detalhes e solicitações

| Método | Endpoint | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/api/v1/catalog/books/{id}` | Pública | Capa, dados bibliográficos e disponibilidade por modalidade |
| `POST` | `/api/v1/loan-requests` | Bearer (`USER`) | Solicitação pendente de empréstimo |
| `POST` | `/api/v1/purchase-requests` | Bearer (`USER`) | Solicitação pendente de compra com retirada no balcão |

Os dois POSTs recebem `{ "book_id": 42, "pickup_date": "2026-10-31" }`.
Retornam HTTP 201 com `id`, `book_id`, `pickup_date`, `status` e `created_at`;
empréstimo também retorna `due_date`, calculada pelo servidor para um mês de
calendário. Campos adicionais como `client_id` ou `due_date` são rejeitados.

Erros: 401 sem sessão; 403 sem papel/cadastro de cliente ou cliente inativo/
penalizado; 404 obra inexistente/inativa; 409 solicitação duplicada ou modalidade
sem disponibilidade; 422 data inválida; 500 falha de persistência, com rollback.
Uma solicitação não registra retirada nem baixa estoque. Empréstimo não retém exemplar; compra disponível destina um comercial por meio de PurchaseReservation.
Consulta local retorna `configured: false` e valores nulos até configuração.

Aplicar `alembic upgrade head` (incluindo 0011, 0012 e 0013) antes de utilizar os fluxos da V2.
Para validar a suíte, migrations e concorrência em um banco descartável no
PostgreSQL local (porta 54322), execute:

```bash
.venv/bin/python scripts/check_v2_requests.py
```

O script cria e remove somente seu banco temporário; não usa o banco da aplicação.

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
- `GET /api/v1/books/metadata/{isbn}`: consulta metadados canônicos no Google Books (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `GET /api/v1/books/{book_id}`: detalhes internos da obra e seus exemplares (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `PATCH /api/v1/books/{book_id}`: altera metadados e link da capa (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `POST /api/v1/books/`: cria obra com primeiro exemplar (`STOCK_KEEPER`, `ADMINISTRATOR`).
- `POST /api/v1/copies/`: adiciona exemplar à obra (`STOCK_KEEPER`, `ADMINISTRATOR`).

## Dados demonstrativos no banco local

Com o Supabase local em execução e as migrations aplicadas, execute a partir
**da pasta `backend`**:

```bash
.venv/bin/python -m scripts.seed_books
```

A seed cria também as contas de `scripts.seed_users`. Ela é restrita a
`APP_ENV=development` e PostgreSQL em localhost. Usa a conexão configurada do
backend (por padrão `127.0.0.1:54322`) e não depende do Google Books.

| Obra demonstrativa | Cenário inicial |
| --- | --- |
| Dom Casmurro | 2 exemplares didáticos disponíveis e 1 comercial por R$ 29,90 |
| Sapiens | 1 exemplar comercial disponível por R$ 49,90 |
| 1984 | 1 exemplar didático com empréstimo aberto: indisponível no catálogo |
| O Pequeno Príncipe | 1 exemplar comercial com empréstimo aberto: indisponível, com `can_reserve` |

Obras e categorias novas ficam em destaque na home. Os ISBNs são fixtures com
checksum válido, não os identificadores das edições reais; capas não são
copiadas de fontes externas. Os empréstimos são dados demonstrativos inseridos
com os triggers e a auditoria do banco; não substituem as operações V2 da API. O prazo de 30 dias dessa fixture não define a política da biblioteca.

A seed preserva registros existentes, não redefine senhas e não reabre
empréstimos depois que você os altera. Executá-la de novo não duplica as obras,
os exemplares ou os empréstimos. Não é necessário resetar o banco.

Contas criadas quando ainda não existem:

- `cliente@libstock.com.br`
- `vendedor@libstock.com.br`
- `estoquista@libstock.com.br`
- `admin@libstock.com.br`

Senha inicial dessas contas: `LibStock@2026`.

Para criar somente as contas:

```bash
.venv/bin/python -m scripts.seed_users
```

## Acompanhamento e circulação V2

Cliente ativo com papel `USER`:

| Método/endpoint | Contrato |
| --- | --- |
| GET `/api/v1/loans/me` | Aguardando retirada, ativos e atrasados do usuário autenticado |
| GET `/api/v1/purchase-reservations/me` | WAITING/NOTIFIED do usuário, posição atual e exemplar destinado |
| POST `/api/v1/purchase-reservations` | Corpo `{ "book_id": 1 }`; cria WAITING sem exemplar comercial livre |

`client_id`, estado e posição enviados pelo cliente são rejeitados. Consultas `/me` ignoram IDs de terceiros em query string. Todos os IDs transacionais novos devem estar entre 1 e 2^63−1.

Funcionário ativo, `SELLER` ou `ADMINISTRATOR`:

| Método/endpoint | Contrato |
| --- | --- |
| POST `/api/v1/staff/loan-requests/{id}/confirm-pickup` | Corpo `{ "copy_id": 1 }`; devolve `{ "id": loan_id }` |
| POST `/api/v1/staff/loans/{id}/confirm-return` | Sem corpo; devolve `{ "id": loan_id }` |
| POST `/api/v1/staff/books/{id}/allocate-purchase` | Sem corpo; atende primeiro WAITING e devolve `{ "id": reservation_id }` |
| POST `/api/v1/staff/purchase-reservations/{id}/confirm-sale` | Sem corpo; conclui venda e devolve `{ "id": sale_id }` |

Empréstimo começa na retirada real, com devolução em um mês de calendário. Clientes penalizados/inativos/com atraso são bloqueados para novas operações; a devolução permanece permitida. A venda exige reserva NOTIFIED e exemplar comercial ativo destinado ao cliente. A baixa SOLD e a conclusão FULFILLED acontecem na mesma transação.

Estados são projeções dos models existentes; NOTIFIED não dispara notificações. Prazo de retirada só é mostrado quando expires_at já existe. A API não implementa ainda cancelamento, expiração automática nem prioridade de fila. As telas operacionais do balcão (`/balcao` no frontend) consomem os endpoints abaixo.

As transições são auditadas e falhas provocam rollback. Sem autenticação: 401; papel/cadastro inelegível: 403; recurso inexistente: 404; conflito operacional: 409; corpo/ID inválido: 422. Erros internos retornam código estável sem revelar SQL.

### Consultas de balcão V2 (somente leitura)

Todos os GET abaixo ficam sob `/api/v1/staff`, exigem `SELLER` ou `ADMINISTRATOR` e funcionário com cadastro ativo (usuário e perfil ativos); caso contrário respondem 403 `employee_record_required`. Sem token: 401; `USER` e `STOCK_KEEPER`: 403 `permission_denied`. `q` é busca parcial sem diferenciar maiúsculas (máx. 100 caracteres; `%` e `_` são literais); `limit` vai de 1 a 100; `client_id` precisa ser inteiro positivo (422 caso contrário). Ordenação determinística. Nenhuma consulta altera dados.

| Endpoint | Parâmetros | Resposta (200) |
| --- | --- | --- |
| GET `/api/v1/staff/clients` | `q` obrigatório (mín. 2 caracteres após aparar, senão 422 `search_term_too_short`), `limit` (padrão 20) | Lista de `{id, name, email, is_active, is_penalized, has_overdue_loan, eligible}`, ordenada por nome. Sem dados administrativos (papéis, hash, telefone) |
| GET `/api/v1/staff/loan-requests` | `q` (cliente/e-mail/obra/autor), `client_id`, `limit` (padrão 50) | Solicitações sem retirada confirmada (`loan_id IS NULL`): `{id, client, book, pickup_date, due_date, created_at, eligible_copies[{id, barcode, condition}]}`, por data de retirada e id. `eligible_copies` usa a mesma definição de exemplar livre da confirmação (didático, ativo, AVAILABLE, sem venda em andamento e não destinado); vazia se a obra está inativa |
| GET `/api/v1/staff/loans` | `q` (também código de barras), `client_id`, `limit` | Empréstimos OPEN: `{id, client, book, copy_id, copy_barcode, loan_date, due_date, status ACTIVE/OVERDUE, days_late}`, por vencimento e id. Atraso pelo calendário de America/Sao_Paulo, igual ao acompanhamento do cliente |
| GET `/api/v1/staff/purchase-reservations` | `q`, `client_id`, `status` (`WAITING`/`NOTIFIED`), `limit` | Reservas WAITING/NOTIFIED: `{id, client, book, status, queue_position, requested_at, pickup_date, notified_at, expires_at, expired, allocated_copy_id, allocated_copy_barcode, free_commercial_copies, can_allocate, allocation_blocked_reason}`. `queue_position` conta WAITING anteriores da obra (nulo em NOTIFIED). `expires_at` só existe se persistido; `expired` apenas o compara com agora |

`client` é `{id, name, email, is_active, is_penalized, has_overdue_loan, eligible}`; `eligible` usa o mesmo predicado de `client_eligibility.py` aplicado nas confirmações. `can_allocate` é verdadeiro somente para a primeira reserva WAITING da obra com cliente elegível e exemplar comercial livre; caso contrário `allocation_blocked_reason` é `NOT_FIRST_IN_QUEUE`, `CLIENT_INELIGIBLE`, `NO_FREE_COPY` ou `BOOK_INACTIVE`. Cliente inelegível na frente da fila continua bloqueando a destinação (sem salto automático).

Pendências do cliente reutilizam o endpoint existente `GET /api/v1/clients/{id}/pendencies` (`SELLER` ou `ADMINISTRATOR`). Limitação técnica herdada: ele sincroniza a penalização automática do cliente antes de responder (efeito de escrita num GET) e não exige cadastro de funcionário ativo.

Erros de consulta inesperados retornam 500 `desk_query_error` sem detalhes de SQL.

Relatório técnico, matriz completa da V2 e roteiro de testes: [V2_REVIEW.md](../docs/V2_REVIEW.md).
