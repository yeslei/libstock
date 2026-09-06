# LibStock

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- PostgreSQL
- Alembic
- Pytest

## Arquitetura

Fluxo padrão:

Controller -> Service -> Repository -> SQLAlchemy

Responsabilidades:

- Controller: HTTP, autenticação, autorização, validação de entrada e status codes.
- Service: regras de negócio, transações e orquestração.
- Repository: consultas e persistência, sem regras de apresentação.
- Schema: contrato de entrada e saída da API.
- Model: mapeamento persistente e constraints estruturais.

Controllers não devem acessar o banco diretamente nem retornar respostas simuladas.

## Regras de negócio

- Não inventar regras de negócio.
- Toda regra nova deve ser registrada em `docs/BUSINESS_RULES.md`.
- Diferenciar explicitamente:
  - regra aprovada;
  - decisão pendente;
  - funcionalidade planejada;
  - limitação técnica;
  - defeito confirmado.
- Não classificar uma funcionalidade futura como defeito da versão atual sem requisito versionado.
- Regras críticas devem ser validadas no service e protegidas por constraints no banco quando aplicável.

## Banco e migrations

- Não alterar migrations já aplicadas.
- Toda alteração estrutural deve criar uma nova migration Alembic.
- Não usar `Base.metadata.create_all()` em produção ou nos testes de integração.
- Migrations devem ser reversíveis quando tecnicamente possível.
- Toda nova entidade deve definir:
  - chave estrangeira;
  - política de exclusão;
  - índices;
  - unicidade;
  - constraints;
  - timestamps;
  - estados permitidos.
- Operações que alteram múltiplas entidades devem ser atômicas.

## Autenticação e autorização

- Toda rota protegida deve declarar sua dependency de autenticação.
- Toda operação administrativa deve declarar os papéis permitidos.
- A autorização deve ser aplicada no backend, mesmo que o frontend também esconda ações.
- Papéis documentados e papéis implementados devem permanecer sincronizados.
- Operações auditáveis devem registrar o funcionário responsável.
- Usuários inativos e funcionários inativos não podem executar operações protegidas.

## APIs

- Não retornar HTTP 2xx para operações não persistidas.
- Usar schemas explícitos de entrada e saída.
- Erros de domínio devem possuir códigos estáveis.
- Status codes devem ser testados.
- Endpoints devem ser documentados no `backend/README.md` ou no contrato oficial da API.
- Alterações incompatíveis devem exigir versionamento ou migração de contrato.

## Testes obrigatórios

Toda feature deve incluir testes para:

- caso de sucesso;
- validação de entrada;
- autorização;
- recurso inexistente;
- conflito de unicidade;
- rollback ou falha de persistência;
- concorrência, quando aplicável;
- integração com o repository;
- migration, quando houver alteração estrutural.

Antes de concluir:

```bash
cd backend
pytest -q
alembic check
alembic upgrade head
alembic downgrade -1
alembic upgrade head