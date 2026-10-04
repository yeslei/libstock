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
| `POST` | `/api/v1/books/` | Bearer (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`) | Cadastra uma obra e seu exemplar inicial ativo na mesma transação |

## Permissionamento

### V2: detalhes e solicitações

| Método | Endpoint | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/api/v1/catalog/books/{id}` | Pública | Capa, dados bibliográficos e disponibilidade por modalidade |
| `GET` | `/api/v1/catalog/genres/{slug}/books` | Pública | Livros da categoria, paginados (`page`, `page_size` até 48); `q` (até 100 caracteres) filtra por título ou autor dentro da categoria |
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
- `GET /api/v1/books/metadata/{isbn}`: consulta metadados canônicos no Google Books (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`).
- `GET /api/v1/books/{book_id}`: detalhes internos da obra e seus exemplares (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`).
- `PATCH /api/v1/books/{book_id}`: altera metadados e link da capa, inativa e reativa a obra (`SELLER`, `STOCK_KEEPER`, `MANAGER`, `ADMINISTRATOR`, funcionário ativo; Issue #151). Reativação (`is_active=true` em obra inativa): exige ao menos um exemplar ativo, senão 409 `book_without_active_copy` (inclusive quando o gatilho `trg_active_book_has_copy` barra o commit), com lock do livro e dos exemplares.
- `POST /api/v1/books/`: cria obra com primeiro exemplar (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`).
- `POST /api/v1/copies/` e `POST /api/v1/copies/batch`: adicionam exemplar(es) à obra (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`, funcionário ativo).
- `PATCH /api/v1/copies/{copy_id}`: edita ou converte exemplar (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`, funcionário ativo; Issue #151). Corpo parcial com `destination`, `condition`, `sale_price` e `acquired_at` (ao menos um; `barcode` e demais campos são 422, o código é imutável). Só para exemplar `AVAILABLE`, ativo, sem destinação a reserva e sem venda em andamento. Conversão para `COMMERCIAL` exige `sale_price` > 0; para `DIDACTIC` o preço é removido. 200 com o exemplar; 401 sem token; 403 `permission_denied` (inclusive `USER`), `user_inactive` ou `employee_record_required`; 404 `copy_not_found`; 409 com `code` do primeiro motivo (`copy_inactive`, `copy_not_available`, `copy_allocated` ou `copy_in_operation`) e `details.reasons[]`, ou 409 `copy_needed_for_requests` ao converter para venda o último didático livre de obra com solicitação de retirada pendente; 422 `copy_sale_price_required`, `copy_sale_price_not_allowed` ou erro de contrato; 500 `copy_update_persistence_error`. Atômica, com lock do livro e depois do exemplar; auditoria com o funcionário (`trg_audit_copies`). A migration `20261003_0014` ajusta o gatilho `guard_copy_integrity` para aceitar `SELLER` e `STOCK_KEEPER` além de `ADMINISTRATOR` na troca de destinação.
- `DELETE /api/v1/copies/{copy_id}`: exclui fisicamente um exemplar `AVAILABLE` e sem histórico (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`, funcionário ativo; auditoria com o funcionário). 200 `{id, book_id, barcode, deleted}`; 401 sem token; 403 `permission_denied` (inclusive `USER`), `user_inactive` ou `employee_record_required`; 404 `copy_not_found`; 409 bloqueio com `code` do primeiro motivo (`copy_not_available`, `copy_has_history` ou `last_active_copy`), `details.reasons[]` e `details.history` (`loans`, `sales`, `purchase_reservations`, `requests`); 500 `copy_delete_persistence_error`. Atômica, com lock do livro e do exemplar; FK ou gatilho do banco que barrem algo não previsto viram 409.
- `POST /api/v1/sales/` (`SELLER`, `ADMINISTRATOR`): venda direta confirmada no ato (Issue #149). Corpo `{client_id?, items: [{copy_id, unit_price?}]}`; `unit_price` está descontinuado e é ignorado, pois o preço de cada item é sempre o `sale_price` cadastrado no exemplar e o `total_amount` é calculado pelo servidor. 201 com `status = CONFIRMED`, itens com o preço do cadastro e exemplares `SOLD` na mesma transação (mesmo mecanismo do confirm-sale V2, com auditoria do funcionário). 404 cliente ou exemplar inexistente ou inativo; 409 exemplar indisponível (inclusive venda concorrente do mesmo exemplar), exemplar didático, `book_inactive` ou `copy_without_price`; 401/403 sem autenticação ou papel. Estorno e cancelamento são funcionalidade planejada.
- `PATCH /api/v1/books/{book_id}` com `is_active=false`: bloqueado com 409 `book_has_active_operations` enquanto houver empréstimo `OPEN` de qualquer exemplar da obra, solicitação de retirada pendente ou reserva de compra `WAITING`/`NOTIFIED`; `details.counts` (`open_loans`, `pending_loan_requests`, `purchase_reservations`) e `details.links` (`type`, `copy_barcode` e, só para `ADMINISTRATOR`/`SELLER`, `client_name`). `POST /api/v1/loans/` e `POST /api/v1/sales/` recusam obra inativa com 409 `book_inactive`, travando o livro antes do exemplar.
- `POST /api/v1/loans/` (`SELLER`, `ADMINISTRATOR`; corpo `{client_id, copy_id}`): empréstimo direto com `due_date` um mês de calendário após `loan_date` em America/Sao_Paulo (ajuste de fim de mês igual ao da retirada V2). Aceita somente exemplar didático, disponível e ativo de obra ativa; erros: 404 exemplar não encontrado, 409 exemplar indisponível, 409 `copy_not_for_loan` (exemplar comercial), 409 `book_inactive`, `client_not_found` (404), `client_inactive` (403), `client_has_pending` (409). O atraso, aqui e em `GET /api/v1/clients/{id}/pendencies` (que sincroniza a penalidade), usa a data de negócio de America/Sao_Paulo, como a V2.

Erros de domínio com dados estruturados respondem `{detail, code, details}`; `details` só existe nesses casos. Regras em [BUSINESS_RULES.md](../docs/BUSINESS_RULES.md), seção 21.

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

Todos os GET abaixo ficam sob `/api/v1/staff`, exigem `SELLER` ou `ADMINISTRATOR` e funcionário com cadastro ativo. Sem token: 401; usuário inativo: 403 `user_inactive` (autenticação); perfil/funcionário inativo ou ausente: 403 `employee_record_required`; `USER` e `STOCK_KEEPER`: 403 `permission_denied`. `q` é busca parcial sem diferenciar maiúsculas (máx. 100 caracteres; `%` e `_` são literais); `limit` vai de 1 a 100; `client_id` precisa ser inteiro positivo (422 caso contrário). Ordenação determinística. Nenhuma consulta altera dados.

| Endpoint | Parâmetros | Resposta (200) |
| --- | --- | --- |
| GET `/api/v1/staff/clients` | `q` obrigatório (mín. 2 caracteres após aparar, senão 422 `search_term_too_short`), `limit` (padrão 20) | Lista de `{id, name, email, is_active, is_penalized, has_overdue_loan, eligible}`, ordenada por nome. Sem dados administrativos (papéis, hash, telefone) |
| GET `/api/v1/staff/loan-requests` | `q` (cliente/e-mail/obra/autor), `client_id`, `limit` (padrão 50) | Solicitações sem retirada confirmada (`loan_id IS NULL`): `{id, client, book, pickup_date, due_date, created_at, eligible_copies[{id, barcode, condition}]}`, por data de retirada e id. `eligible_copies` usa a mesma definição de exemplar livre da confirmação (didático, ativo, AVAILABLE, sem venda em andamento e não destinado); vazia se a obra está inativa |
| GET `/api/v1/staff/loans` | `q` (também código de barras), `client_id`, `limit` | Empréstimos OPEN: `{id, client, book, copy_id, copy_barcode, loan_date, due_date, status ACTIVE/OVERDUE, days_late}`, por vencimento e id. Atraso pelo calendário de America/Sao_Paulo, igual ao acompanhamento do cliente |
| GET `/api/v1/staff/purchase-reservations` | `q`, `client_id`, `status` (`WAITING`/`NOTIFIED`), `limit` | Reservas WAITING/NOTIFIED: `{id, client, book, status, queue_position, requested_at, pickup_date, notified_at, expires_at, expired, allocated_copy_id, allocated_copy_barcode, free_commercial_copies, can_allocate, allocation_blocked_reason}`. `queue_position` conta WAITING anteriores da obra (nulo em NOTIFIED). `expires_at` só existe se persistido; `expired` apenas o compara com agora |

`client` é `{id, name, email, is_active, is_penalized, has_overdue_loan, eligible}`; `eligible` usa o mesmo predicado de `client_eligibility.py` aplicado nas confirmações. `can_allocate` é verdadeiro somente para a primeira reserva WAITING da obra com cliente elegível e exemplar comercial livre; caso contrário `allocation_blocked_reason` é `NOT_FIRST_IN_QUEUE`, `CLIENT_INELIGIBLE`, `NO_FREE_COPY` ou `BOOK_INACTIVE`. Cliente inelegível na frente da fila continua bloqueando a destinação (sem salto automático).

GET `/api/v1/staff/books` (`q` por título, autor ou ISBN com ou sem hífens, `limit` padrão 50): somente leitura, devolve `{id, title, author, isbn, genre, is_active, total_copies, didactic_copies, commercial_copies}`, por título e id. As contagens consideram exemplares ativos e não vendidos. `GET /api/v1/staff/books/{id}` (id inteiro positivo; 404 `book_not_found`) devolve o mesmo item e `copies[{id, barcode, destination, status, condition, sale_price, is_active, free, allocated_for_purchase}]`, onde `free` usa a definição comum de exemplar livre. Mesmos papéis e guard.

GET `/api/v1/staff/copies` (`q` obrigatório por código, ISBN, título ou autor; sem termo, 422 `search_term_required`; `limit` padrão 20): exemplares ativos com a obra, `free`, `free_commercial_copies`, `sellable` e `sale_block_reason` (`DIDACTIC` ou `NOT_AVAILABLE`). Somente leitura; não cria venda.

A edição de categoria e a inativação de obra na tela do acervo usam o endpoint existente `PATCH /api/v1/books/{id}` (`SELLER`, `STOCK_KEEPER`, `MANAGER`, `ADMINISTRATOR`; `USER` recebe 403). A inclusão de exemplar no balcão usa o endpoint existente `POST /api/v1/copies/` (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`; 409 em código duplicado, 404 em obra inexistente ou inativa, 422 se o preço de venda faltar para `COMMERCIAL` ou for informado para `DIDACTIC`). A reativação de obra (`is_active=true`) exige exemplar ativo (409 `book_without_active_copy`). A inativação é bloqueada (409 `book_has_active_operations`) enquanto houver empréstimo em aberto, solicitação de retirada pendente ou reserva de compra aguardando ou com exemplar destinado. A exclusão de exemplar no balcão usa `DELETE /api/v1/copies/{id}` (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR`; 409 `copy_not_available`, `copy_has_history` ou `last_active_copy`, 404 `copy_not_found`). A edição e a conversão de exemplar usam `PATCH /api/v1/copies/{id}` (409 `copy_inactive`, `copy_not_available`, `copy_allocated` ou `copy_in_operation`; 422 `copy_sale_price_required` ou `copy_sale_price_not_allowed`; 404 `copy_not_found`; BUSINESS_RULES seção 21). `GET /api/v1/staff/loans` também filtra `q` pelo ISBN da obra.

GET `/api/v1/staff/clients/{client_id}/pendencies` (mesmos papéis e guard; 404 `client_not_found`; `client_id` inteiro positivo): somente leitura, devolve `{client: {id, name, email, is_active, is_penalized, has_overdue_loan, eligible}, overdue_loans: [mesmo item de /staff/loans com status OVERDUE e days_late]}`. Atraso pela regra V2 (data de negócio em America/Sao_Paulo; vencer hoje não é atraso). Não grava nada nem sincroniza penalidade.

GET `/api/v1/staff/dashboard` (mesmos papéis e guard; sem parâmetros): somente leitura, devolve `{active_loans, returns_today, waiting_reservations, pendencies}`, inteiros. `active_loans` = empréstimos `OPEN`; `returns_today` = empréstimos com `returned_at` dentro da data atual de America/Sao_Paulo (de 00:00 inclusive até 00:00 do dia seguinte, exclusive); `waiting_reservations` = reservas de compra `WAITING` (reservas `NOTIFIED` não contam); `pendencies` = clientes distintos com ao menos um empréstimo `OPEN` em atraso pela regra V2 (mesma condição de `has_overdue_loan`: `due_date` anterior ao início do dia de negócio atual).

O endpoint legado `GET /api/v1/clients/{id}/pendencies` não é usado pelo balcão: ele sincroniza a penalização automática (escreve num GET), usa `due_date < now()` e não exige funcionário ativo. Comportamento herdado, não alterado.

Erros de consulta inesperados retornam 500 `desk_query_error` sem detalhes de SQL.

Relatório técnico, matriz completa da V2 e roteiro de testes: [V2_REVIEW.md](../docs/V2_REVIEW.md).
