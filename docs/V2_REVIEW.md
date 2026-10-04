# Revisão técnica e repasse da V2

Data: 03/10/2026. Escopo: alterações locais do LibStock, incluindo arquivos novos que não aparecem em `git diff --stat`. A quantidade exibida pelo IDE pode agrupar diretórios; o inventário ao final lista arquivos individualmente. Revisão estática, testes automatizados e verificação de migrations não equivalem à homologação de toda a V2.

## Achados corrigidos

| Prioridade | Problema confirmado | Correção e evidência |
| --- | --- | --- |
| P1 | Solicitações de empréstimo/compra verificavam `is_penalized`, mas não empréstimos OPEN atrasados; a reserva verificava ambos | Política comum em `client_eligibility.py`, usada pelas solicitações, reservas e circulação. Testes rejeitam novas solicitações com atraso |
| P1 | Exemplar destinado mantinha AVAILABLE e poderia alimentar uma venda de outro cliente ou um empréstimo pelo domínio legado | Migration 0013 protege venda, empréstimo, inativação, conversão e troca de obra. Testes PostgreSQL tentam essas operações diretamente e verificam rollback |
| P1 | Cards usavam disponibilidade física; Detalhes excluía destinações e vendas pendentes | Consulta comum em `inventory_availability.py` e projeção do catálogo por IDs livres/reserváveis. Teste compara cards e Detalhes após destinar um exemplar |
| P1 | Refresh antigo podia restaurar sessão após logout, ou limpar login mais recente ao falhar | Geração de sessão em AuthService. Testes simulam respostas fora de ordem |
| P1 | Guards de autenticação e papel tinham tempos diferentes de restauração | Ambos aguardam a mesma restauração; teste executa guards juntos com sessão inicialmente vazia |
| P2 | Resposta de solicitação do livro anterior podia atualizar a tela do próximo livro | Cancelamento de subscriptions ao mudar o ID e verificação da versão após aguardar autenticação |
| P2 | `ClientTrackingService` fazia SQL e operações do funcionário; compra herdava repository de empréstimo; calendário de compra importava service de empréstimo | CirculationController/Service/Repository separados. Base comum de persistência, calendário em core e política comum de elegibilidade |
| P2 | Criação da reserva retornava a ordem persistida, incluindo clientes já atendidos, diferente da posição em acompanhamento | Resposta de criação usa a mesma contagem WAITING; teste diferencia ordem interna 2 de posição atual 1 |
| P2 | Repository de compra decidia se a fila deveria ser atendida | Decisão transferida para PurchaseRequestService; repository recebe o exemplar já escolhido |
| P2 | Locks eram adquiridos em ordens diferentes entre solicitação e destinação | Fluxos que disputam a mesma obra passam a travar obra antes de cliente/reserva; leituras anteriores ao lock são atualizadas com `populate_existing` |
| P2 | Service de circulação só verificava existência do funcionário | Repository exige usuário/perfil ativo. A autenticação existente já verificava perfil; a proteção agora também existe no service e é testada |
| P2 | Trigger da devolução substituía o ator da transação pelo funcionário da retirada original | Migration 0013 preserva ator corrente e audita empréstimos/reservas. Teste confirma devolução por outro funcionário sem mudar responsável pela retirada |
| P2 | IDs positivos sem limite podiam ultrapassar bigint e produzir erro SQL | IDs novos limitados a 1…2^63−1; testes de corpo e rota inválidos verificam 422 antes do service |
| P2 | Operações do cliente estavam no CatalogService, e acompanhamento dependia do tipo de carregamento do catálogo | ClientRequestsService separado; LoadState em core; contratos de HTTP cobertos por testes |
| P3 | Módulo Explorar acervo permanecia sem rota, duplicando a busca e mantendo testes de tela inacessível | Componente antigo removido; redirecionamento `/explorar` preservado; regressão de respostas antigas transferida para a home |

As migrations 0011/0012 já aplicadas foram preservadas. A 0013 é incremental e não cria models ou novos estados de reserva. Foi aplicada ao banco local após validação; produção não foi alterada. `LoanRequest.loan_id` identifica retirada confirmada; `PurchaseRequest.reservation_id` aponta para o domínio operacional PurchaseReservation.

## O que ainda falta da V2

“Implementado” significa fluxo disponível no código atual. “Parcial” identifica uma parte funcional, com a pendência descrita. Nenhuma linha representa homologação em produção.

| EAP | Requisito | Estado | Entrega que falta / critério de aceite |
| --- | --- | --- | --- |
| 1.2.1 | Consulta e atualização de usuários | Implementado | Homologar o fluxo administrativo existente com os papéis oficiais |
| 1.2.2 | Inativação de usuários | Implementado | Homologar bloqueio de acesso, revogação de sessões e proteção do último administrador |
| 1.2.3 | Controle de pendências | Parcial | Atraso e penalidade bloqueiam novas operações. Falta gestão pelo funcionário, regra de regularização e auditoria de aplicação/remoção de penalidade |
| 1.2.4 | Inativação de obras | Pendente | Endpoint/tela e política para obra com empréstimos, solicitações e reservas em andamento; transação auditada |
| 1.2.5 | Quantidade de exemplares | Parcial | Cadastro e mudanças físicas por empréstimo/venda existem. Falta gestão operacional por exemplar, filtros e indicação de quantidades por estado |
| 1.2.6 | Conversão de categoria do acervo | Pendente | Endpoint/tela para destinação DIDACTIC/COMMERCIAL, papel autorizado, preço obrigatório e bloqueios de operações em andamento |
| 1.2.7 | Consulta de disponibilidade | Implementado no recorte | Home/Detalhes consultam disponibilidade real por modalidade. Consulta local não configurada, conforme decisão do usuário |
| 1.2.8 | Sinalização Venda/Empréstimo/Esgotado | Implementado | Homologar casos mistos e sinalização após destinação/venda/retirada |
| 1.2.9 | Validação da situação do cliente | Implementado no recorte | Política comum considera usuário/perfil ativo, penalidade e atraso. Gestão de pendências continua em 1.2.3 |
| 1.2.10 | Registro de empréstimo | Implementado no recorte | Solicitação, consulta e confirmação pela tela `/balcao` (Issue #122), com busca por cliente/obra e escolha do exemplar. Falta homologação com navegador e contas reais |
| 1.2.11 | Cálculo de devolução | Implementado | Um mês de calendário após retirada real; fim de mês e ano bissexto testados |
| 1.2.12 | Status do exemplar | Implementado no recorte | OPEN aplica BORROWED e devolução aplica AVAILABLE atomicamente; falta homologar telas do balcão |
| 1.2.13 | Comprovante digital | Pendente | Gerar comprovante persistente após retirada confirmada, com acesso do titular/funcionário e dados aprovados |
| 1.2.14 | Registro de devolução | Implementado no recorte | Aba Devoluções do balcão lista empréstimos ativos e confirma a devolução. Falta homologação com navegador |
| 1.2.15 | Disponibilidade para venda | Implementado no recorte | Considera vendas em andamento e destinações; revalida antes da conclusão |
| 1.2.16 | Bloqueio de venda didática | Implementado | API e banco rejeitam didáticos; teste da fila também os exclui |
| 1.2.17 | Registro de venda | Parcial | Confirmação de venda vinculada à reserva existe e tem tela no balcão. Venda direta no balcão requer contrato/fluxo próprio se fizer parte do aceite |
| 1.2.18 | Estoque após venda | Implementado no recorte | CONFIRMED aplica SOLD e conclui a reserva; teste de falha mantém estoque/reserva anteriores |
| 1.2.19 | Reserva de compra | Implementado no recorte | Detalhes solicita compra disponível ou entra na espera sem disponibilidade; ambos aparecem em Minhas reservas |
| 1.2.20 | Validação do cliente para reserva | Implementado | Identidade do token e política comum; campos de identidade/estado/fila rejeitados |
| 1.2.21 | Registro da reserva | Implementado | PurchaseReservation é a fonte dos estados operacionais; intenção de retirada disponível fica vinculada em PurchaseRequest |
| 1.2.22 | Fila de reservas | Parcial | FIFO, posição real e tela do funcionário (consulta e destinação manual) existem; prazo, expiração, cancelamento e primeiro elegível entregues na Issue #150; falta apenas atendimento automático ao repor/devolver |
| 1.2.23 | Testes de usuários e acesso | Parcial | Suítes existentes + identidade `/me`, papéis, restauração e respostas fora de ordem. Falta homologação ponta a ponta com contas reais de cada papel |
| 1.2.24 | Testes de acervo | Parcial | Cadastro/metadados e proteção do exemplar destinado cobertos. Inativação/conversão completas dependem dos fluxos pendentes |
| 1.2.25 | Testes de empréstimo/devolução | Parcial | Transições, atraso, duplicidade e rollback cobertos. Falta comprovante e teste de navegador integrando a futura tela do funcionário |
| 1.2.26 | Testes de vendas | Parcial | Venda vinculada à reserva, concorrência, bloqueios e rollback cobertos. Tela/venda direta dependem do contrato restante |
| 1.2.27 | Testes de consulta/reserva | Parcial | Modalidades, reserva, identidade, FIFO e posição testados. Cancelamento e expiração testados na Issue #150; falta recuperação de dados legados |

## Ordem sugerida para os devs

1. **P1 (entregue na Issue #122, pendente de homologação) — Balcão de empréstimos/devoluções:** criar consultas protegidas de solicitações e empréstimos por e-mail/código, conectar as confirmações existentes e impedir ações do cliente. Aceite: pendente → ativo → devolvido sem SQL manual.
2. **P1 (entregue na Issue #122, pendente de homologação) — Balcão de compras/fila:** listar WAITING/NOTIFIED, destinar ao primeiro da fila e concluir a venda. Aceite: nenhuma venda a outro cliente, nenhuma baixa antes da confirmação e reserva concluída desaparece da área do cliente.
3. **P1 — Comprovante digital:** definir conteúdo, persistir após retirada e restringir acesso. A solicitação pendente não gera comprovante de empréstimo ativo.
4. **P1 — Gestão de acervo:** finalizar inativação, quantidades e conversão com transações, permissões e impedimentos por operação em andamento.
5. **P1 — Pendências:** aprovar responsáveis e regra de regularização; implementar auditoria e telas. Não apagar automaticamente `is_penalized` ao devolver, pois o motivo da penalidade não está modelado.
6. **Resolvido (Issue #150) — Ciclo completo da fila:** prazo de retirada de 5 dias corridos, expiração preguiçosa, cancelamento (cliente e balcão) e destinação à primeira reserva elegível foram aprovados e implementados (BUSINESS_RULES, seção 19). Pendente: prazo para reservas criadas por solicitação de compra com exemplar disponível, notificação e expiração agendada.
7. **P2 — Homologação/escala:** testes completos no navegador, paginação de consultas/listas, posições da fila em lote (hoje há uma consulta de posição por reserva WAITING) e revisão de acessibilidade/responsividade das telas operacionais.

Não entram neste repasse: histórico do cliente, notificações V3, pagamentos online ou prioridade complexa de fila. Consulta local continua explicitamente não configurada.

## Pontos de atenção antes de publicar

- **Dados legados/migration 0012:** validar em uma cópia representativa do banco. O backfill de PurchaseRequest pode cancelar intenções sem disponibilidade/cliente elegível. Solicitações de empréstimo anteriores não são automaticamente reconciliadas com empréstimos já existentes; confirmar correspondências sem inferir pela obra apenas. Este é trabalho de migração pendente, não um problema resolvido pelos testes de banco novo.
- **Downgrade para 0011:** os índices antigos são únicos por cliente/obra, sem distinguir histórico. Depois de múltiplas operações legítimas do mesmo cliente, o downgrade de 0012 pode falhar. Não remover histórico para forçar rollback; planejar restauração/reconciliação. O downgrade validado nesta revisão é de 0013 para 0012.
- **Dados NOTIFIED legados sem allocated_copy_id:** o schema anterior permitia esse caso. A tela identifica a ausência do exemplar; a venda exige destinação explícita. Reconciliar antes de prometer retirada.
- **Empréstimos:** solicitação não retém exemplar, portanto a retirada revalida estoque. Não anunciar garantia de retirada com base na solicitação.
- **Compras:** destinação é uma indisponibilidade lógica; o estado físico AVAILABLE é preservado até venda. Consultas futuras de estoque devem reutilizar a disponibilidade comum, em vez de verificar só `Copy.status`.
- **Migrations/produção:** aplicar upgrade antes do backend. Nada foi publicado ou enviado para os devs por serviço externo nesta revisão.

## Endpoints para integrar

| Papel | Método e endpoint | Uso |
| --- | --- | --- |
| Público | GET `/api/v1/catalog/books/{id}` | Detalhes/modalidades |
| USER | POST `/api/v1/loan-requests` | `{book_id, pickup_date}` |
| USER | POST `/api/v1/purchase-requests` | `{book_id, pickup_date}` para compra disponível |
| USER | POST `/api/v1/purchase-reservations` | `{book_id}` para espera |
| USER | GET `/api/v1/loans/me` | Pendentes/ativos/atrasados próprios |
| USER | GET `/api/v1/purchase-reservations/me` | Reservas de compra próprias em andamento |
| SELLER/ADMINISTRATOR | GET `/api/v1/staff/clients?q=` | Busca de clientes (mín. 2 caracteres) |
| SELLER/ADMINISTRATOR | GET `/api/v1/staff/loan-requests` | Solicitações pendentes com exemplares elegíveis |
| SELLER/ADMINISTRATOR | GET `/api/v1/staff/loans` | Empréstimos ativos e atraso |
| SELLER/ADMINISTRATOR | GET `/api/v1/staff/purchase-reservations` | Reservas WAITING/NOTIFIED e `can_allocate` |
| SELLER/ADMINISTRATOR | GET `/api/v1/staff/clients/{id}/pendencies` | Pendências somente leitura (regra V2) |
| SELLER/ADMINISTRATOR | POST `/api/v1/staff/loan-requests/{id}/confirm-pickup` | `{copy_id}`; devolve ID do Loan |
| SELLER/ADMINISTRATOR | POST `/api/v1/staff/loans/{id}/confirm-return` | Sem corpo |
| SELLER/ADMINISTRATOR | POST `/api/v1/staff/books/{id}/allocate-purchase` | Sem corpo; primeiro WAITING |
| SELLER/ADMINISTRATOR | POST `/api/v1/staff/purchase-reservations/{id}/confirm-sale` | Sem corpo; devolve ID do Sale |

Funcionário deve possuir registro Employee e usuário/perfil ativo. IDs de cliente não são aceitos nos corpos de solicitação.

## Roteiro manual de aceite

Usar ambiente local/homologação, duas contas USER e uma SELLER/ADMINISTRATOR. Aplicar `alembic upgrade head`. Como a tela do funcionário ainda não existe, suas operações podem ser chamadas em `/docs` local com o token da conta autorizada.

1. **Vazio:** acessar as duas telas com cliente sem operações; verificar os textos exatos “Você não possui empréstimos ou solicitações em andamento.” e “Você não possui reservas de compra em andamento.” Um erro de API deve mostrar erro/retry, nunca vazio.
2. **Empréstimo pendente:** pesquisar obra com didático livre, abrir Detalhes, informar retirada e confirmar. Verificar snackbar após resposta 201 e Aguardando retirada, com a data solicitada e orientação de e-mail no balcão.
3. **Retirada:** chamar confirm-pickup com ID da solicitação e didático da mesma obra. Verificar empréstimo ativo, data real, prazo de um mês e exemplar BORROWED. Repetição deve gerar conflito, sem novo empréstimo.
4. **Atraso:** em fixture isolada criar empréstimo com vencimento anterior à data de negócio, ou executar o teste com relógio controlado. Verificar Em atraso e dias corretos, e bloqueio de nova solicitação. Não mudar o relógio da máquina nem editar empréstimo real para fabricar atraso.
5. **Devolução:** chamar confirm-return; verificar exemplar AVAILABLE e ausência do item em Meus empréstimos. Devolver atraso continua permitido.
6. **Compra disponível:** solicitar compra em Detalhes com comercial livre; verificar NOTIFIED e identificação do exemplar em Minhas reservas. Outro cliente não deve ver esse exemplar como livre.
7. **Espera/FIFO:** usar obra com comercial BORROWED/RESERVED ou já destinado, sem comercial livre. Reservar com dois clientes, verificar posições 1 e 2. Após devolver/repor comercial, chamar allocate-purchase; primeiro fica NOTIFIED e segundo passa a posição 1.
8. **Venda:** chamar confirm-sale com reserva NOTIFIED. Verificar SOLD, FULFILLED e remoção de Minhas reservas. Uma segunda confirmação gera conflito.
9. **Segurança:** repetir endpoints staff como USER (403), sem sessão (401), e adicionar client_id/status/queue_position ao corpo (422). Query client_id de terceiro em `/me` não altera titular. Didático nunca habilita compra/fila.
10. **Revisão visual:** verificar busca/cards/Detalhes/acompanhamento em desktop e celular, textos longos, capa ausente, teclado, erro e lista vazia. Ajustes recentes do header foram preservados.

## Validação automatizada

- Backend: suíte completa em PostgreSQL temporário criado por `scripts/check_v2_requests.py`; inclui testes reais de repositories/triggers, autorização, calendário, FIFO, concorrência e rollback.
- Frontend: ChromeHeadless, incluindo sessão, guards, busca na home, solicitação/reserva, navegação durante envio, contratos HTTP e empty states.
- Migrations: upgrade completo, `alembic check`, downgrade 0013 → 0012 e novo upgrade em banco descartável. Nenhum `create_all()` foi usado.
- O runner descarta somente o banco de teste que criou, sem fazer downgrade/reset no banco da aplicação.

Comandos:

```bash
cd backend
.venv/bin/python scripts/check_v2_requests.py
cd ../frontend
npm test -- --watch=false --browsers=ChromeHeadless
npm run build
```

Resultado final: **219 testes de backend aprovados, 124 testes Angular aprovados e build de produção aprovado**. `alembic check`, upgrade, downgrade de 0013 e novo upgrade passaram no banco temporário. `git diff --check` passou. Existe um aviso de depreciação Starlette/httpx na infraestrutura de TestClient; não é uma falha funcional da V2.

## Arquivos principais da revisão

- Backend: `core/business_dates.py`, `repositories/client_request_repository.py`, `repositories/inventory_availability.py`, `services/client_eligibility.py`, `controllers/circulation_controller.py`, `services/circulation_service.py`, `repositories/circulation_repository.py` e os fluxos de catálogo/solicitações/acompanhamento.
- Banco: nova migration `20261003_0013_protect_allocated_copies.py`; migrations já aplicadas preservadas.
- Frontend: `core/models/load-state.model.ts`, `role.guard.ts`, `auth.service.ts`, `client-requests.service.ts`, Detalhes e testes; componente antigo de Explorar removido.
- Testes: `test_v2_review.py`, `test_circulation_service.py`, contratos de acompanhamento e regressões Angular.
- Repasse: este documento, `BUSINESS_RULES.md`, `V2_IMPLEMENTATION.md` e `backend/README.md`.

O inventário abaixo inclui as alterações anteriores do workspace; não atribui todas elas a esta revisão.


### Inventário do workspace após a revisão

95 arquivos alterados/novos/removidos em relação ao checkout, incluindo esta documentação:

```text
backend/README.md
backend/app/controllers/catalog_controller.py
backend/app/controllers/circulation_controller.py
backend/app/controllers/client_tracking_controller.py
backend/app/controllers/loan_request_controller.py
backend/app/controllers/purchase_request_controller.py
backend/app/core/business_dates.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/models/domain.py
backend/app/models/loan_request.py
backend/app/models/purchase_request.py
backend/app/repositories/catalog_repository.py
backend/app/repositories/circulation_repository.py
backend/app/repositories/client_request_repository.py
backend/app/repositories/client_tracking_repository.py
backend/app/repositories/inventory_availability.py
backend/app/repositories/loan_request_repository.py
backend/app/repositories/purchase_request_repository.py
backend/app/schemas/catalog_schema.py
backend/app/schemas/client_tracking_schema.py
backend/app/schemas/loan_request_schema.py
backend/app/schemas/purchase_request_schema.py
backend/app/services/catalog_service.py
backend/app/services/circulation_service.py
backend/app/services/client_eligibility.py
backend/app/services/client_tracking_service.py
backend/app/services/loan_request_service.py
backend/app/services/purchase_request_service.py
backend/migrations/versions/20261003_0011_loan_requests.py
backend/migrations/versions/20261003_0012_client_tracking.py
backend/migrations/versions/20261003_0013_protect_allocated_copies.py
backend/scripts/check_v2_requests.py
backend/scripts/seed_books.py
backend/tests/test_catalog.py
backend/tests/test_circulation_service.py
backend/tests/test_client_requests_postgres.py
backend/tests/test_client_tracking.py
backend/tests/test_loan_requests.py
backend/tests/test_purchase_requests.py
backend/tests/test_tracking_postgres.py
backend/tests/test_v2_review.py
docs/BUSINESS_RULES.md
docs/V2_IMPLEMENTATION.md
docs/V2_REVIEW.md
frontend/assets/home-reading.png
frontend/src/app/app.config.ts
frontend/src/app/app.routes.ts
frontend/src/app/core/guards/auth.guard.ts
frontend/src/app/core/guards/guest.guard.ts
frontend/src/app/core/guards/role.guard.spec.ts
frontend/src/app/core/guards/role.guard.ts
frontend/src/app/core/guards/session.guards.spec.ts
frontend/src/app/core/models/load-state.model.ts
frontend/src/app/core/services/auth.service.spec.ts
frontend/src/app/core/services/auth.service.ts
frontend/src/app/features/auth/auth-layout/auth-layout.component.html
frontend/src/app/features/auth/auth-layout/auth-layout.component.scss
frontend/src/app/features/auth/login/login.component.html
frontend/src/app/features/catalog/book-details/book-details.component.html
frontend/src/app/features/catalog/book-details/book-details.component.scss
frontend/src/app/features/catalog/book-details/book-details.component.spec.ts
frontend/src/app/features/catalog/book-details/book-details.component.ts
frontend/src/app/features/catalog/book-details/loan-dates.spec.ts
frontend/src/app/features/catalog/book-details/loan-dates.ts
frontend/src/app/features/catalog/catalog-home/catalog-home.component.html
frontend/src/app/features/catalog/catalog-home/catalog-home.component.scss
frontend/src/app/features/catalog/catalog-home/catalog-home.component.spec.ts
frontend/src/app/features/catalog/catalog-home/catalog-home.component.ts
frontend/src/app/features/catalog/components/catalog-book-card/catalog-book-card.component.html
frontend/src/app/features/catalog/components/catalog-book-card/catalog-book-card.component.scss
frontend/src/app/features/catalog/components/catalog-book-card/catalog-book-card.component.ts
frontend/src/app/features/catalog/explore-books/explore-books.component.html
frontend/src/app/features/catalog/explore-books/explore-books.component.scss
frontend/src/app/features/catalog/explore-books/explore-books.component.spec.ts
frontend/src/app/features/catalog/explore-books/explore-books.component.ts
frontend/src/app/features/catalog/genre-books/genre-books.component.html
frontend/src/app/features/catalog/genre-books/genre-books.component.scss
frontend/src/app/features/catalog/genre-books/genre-books.component.ts
frontend/src/app/features/catalog/models/catalog.model.ts
frontend/src/app/features/catalog/services/catalog.service.ts
frontend/src/app/features/client-tracking/client-requests.service.ts
frontend/src/app/features/client-tracking/client-services.spec.ts
frontend/src/app/features/client-tracking/client-tracking.component.html
frontend/src/app/features/client-tracking/client-tracking.component.scss
frontend/src/app/features/client-tracking/client-tracking.component.spec.ts
frontend/src/app/features/client-tracking/client-tracking.component.ts
frontend/src/app/features/client-tracking/client-tracking.service.ts
frontend/src/app/shared/components/app-navbar/app-navbar.component.html
frontend/src/app/shared/components/app-navbar/app-navbar.component.scss
frontend/src/app/shared/components/app-navbar/app-navbar.component.spec.ts
frontend/src/app/shared/components/app-navbar/app-navbar.component.ts
frontend/src/styles/_auth-screen.scss
frontend/src/styles/_variables.scss
frontend/vercel.json
```
