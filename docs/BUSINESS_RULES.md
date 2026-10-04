# Regras de negócio do LibStock

## 1. Objetivo do sistema

O LibStock gerencia obras bibliográficas, exemplares físicos e operações de
circulação. O sistema distingue:

- obra bibliográfica;
- exemplar físico;
- cliente;
- funcionário;
- papel de acesso;
- operação de empréstimo, reserva, venda ou troca.

Este documento define regras de negócio, invariantes e decisões de escopo.
Não substitui a documentação técnica da API nem as migrations.

## 2. Escopo da versão analisada

### Implementado

- autenticação e sessões;
- consulta pública do catálogo;
- busca por título, autor, ISBN e código de barras;
- cadastro inicial de obras;
- gestão de destaques.

### Parcialmente implementado

- cadastro de funcionários;
- disponibilidade derivada dos exemplares;
- controle de papéis;
- persistência de entidades de circulação;
- vendas: venda direta confirmada no ato, com exemplar `SOLD` e preço do cadastro (Issue #149), e bloqueio de venda de exemplares didáticos implementados; estorno e cancelamento de venda seguem como funcionalidade planejada.

### Planejado, mas não disponível

- reservas;
- trocas;
- notificações;
- gestão operacional de exemplares.

A existência de tabelas, enums ou views não significa que o fluxo esteja
disponível pela API.

## 3. Vocabulário do domínio

| Termo | Definição |
|---|---|
| Obra | Registro bibliográfico identificado por ISBN, título e autor |
| Exemplar | Unidade física vinculada a uma obra |
| Cliente | Usuário que pode participar de operações de circulação |
| Funcionário | Usuário responsável por operações internas |
| Catálogo | Projeção pública de obras visíveis |
| Disponibilidade | Estado derivado dos exemplares ativos |
| Papel | Código técnico usado para autorização |
| Operação | Alteração transacional de acervo ou circulação |

## 4. Status das regras

Cada regra deve ter um status explícito:

- `IMPLEMENTED`: implementada na API e coberta por testes;
- `PARTIAL`: parcialmente implementada;
- `APPROVED`: decisão aprovada, ainda não necessariamente implementada;
- `PENDING`: depende de decisão de negócio;
- `OUT_OF_SCOPE`: não pertence à versão documentada.

Cada seção deve informar também:

- versão-alvo;
- endpoint relacionado;
- entidades envolvidas;
- testes esperados.

## 5. Atores e permissões

| Ator/papel | Capacidades |
|---|---|
| `USER` | consultar catálogo e operar conforme regras de cliente |
| `SELLER` | atendimento e operações de balcão; administra o acervo (cadastrar, editar, inativar e reativar obra; incluir, editar/converter e excluir exemplar) |
| `STOCK_KEEPER` | cadastrar obras e operar acervo (mesmas operações de acervo do `SELLER`) |
| `ADMINISTRATOR` | administrar funcionários, papéis e configurações, além de todas as operações de acervo e de balcão |

Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (decisão 6, implementada na Issue #151): o LibStock é um ERP de biblioteca, com possibilidade de totem de autoatendimento, e os vendedores administram a operação. Por isso `SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR` podem, no backend (`require_roles`) e na tela do balcão:

| Operação de acervo | Endpoint | Papéis |
|---|---|---|
| Cadastrar obra (com primeiro exemplar) | `POST /api/v1/books/` | `SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR` |
| Consultar metadados por ISBN e detalhe interno da obra | `GET /api/v1/books/metadata/{isbn}`, `GET /api/v1/books/{id}` | `SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR` |
| Editar, inativar e reativar obra | `PATCH /api/v1/books/{id}` | `SELLER`, `STOCK_KEEPER`, `MANAGER` (herdado, sem papel equivalente nos papéis oficiais), `ADMINISTRATOR` |
| Incluir exemplar (unitário e em lote) | `POST /api/v1/copies/`, `POST /api/v1/copies/batch` | `SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR` |
| Editar e converter exemplar | `PATCH /api/v1/copies/{id}` | `SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR` |
| Excluir exemplar | `DELETE /api/v1/copies/{id}` | `SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR` |

Cadastrar obra nova também é do `SELLER`, pois ele administra o acervo e a inclusão de exemplar já lhe é permitida (decisão da Issue #151 com base na matriz acima). `USER` recebe 403 `permission_denied` em todas; sem token, 401. As operações com auditoria exigem funcionário com cadastro ativo (perfil e usuário ativos); caso contrário, 403 `employee_record_required` (ou `audit_actor_required` na inclusão de exemplar). A gestão de usuários, funcionários e papéis continua exclusiva do `ADMINISTRATOR`.

Os códigos acima são técnicos e não devem ser substituídos por nomes exibidos na
interface. Toda permissão deve ser validada no backend.

## 6. Invariantes gerais

- Toda obra ativa precisa obedecer ao contrato de dados definido nesta
  documentação.
- Exemplar inativo não participa da disponibilidade.
- Operações que alteram mais de uma entidade devem ser atômicas.
- HTTP 2xx só pode ser retornado após conclusão da operação.
- Conflitos de unicidade ou concorrência devem resultar em erro explícito.
- Toda alteração operacional deve identificar o funcionário responsável,
  quando aplicável.
- Migrations antigas não são alteradas; novas mudanças exigem nova migration.

## 7. Catálogo e visibilidade

Uma obra aparece no catálogo quando:

- `books.is_active = true`;
- existe pelo menos um exemplar ativo.

Uma obra sem exemplar disponível continua visível, mas deve indicar
indisponibilidade.

A resposta pública permanece no nível de obra. Dados internos do exemplar,
como identificador físico ou estado detalhado, não são expostos sem regra
específica.

## 8. Busca

### Título e autor

- substring;
- case-insensitive;
- trim nas extremidades;
- entrada vazia inválida;
- `%` e `_` tratados literalmente;
- somente obras visíveis.

### ISBN

Separar explicitamente:

#### Busca

- correspondência exata;
- trim nas extremidades;
- sem remoção de hífens;
- sem conversão entre ISBN-10 e ISBN-13;
- sem validação de checksum durante a busca.

#### Cadastro

Regra aprovada e implementada:

- ISBN é obrigatório;
- aceita ISBN-10 ou ISBN-13;
- espaços e hífens são aceitos na entrada;
- o valor é armazenado normalizado, sem espaços ou hífens;
- o checksum é validado;
- o backend é a autoridade final sobre normalização e validade.

## 9. Exemplares e estados

Regra aprovada: a obra pode armazenar um `cover_url` opcional. O valor deve ser
uma URL absoluta HTTP ou HTTPS. O sistema apenas referencia a imagem externa;
não realiza upload nem copia o arquivo para o servidor. Uma falha de validação
ou persistência durante a edição preserva o valor anteriormente confirmado.

- Estado: `IMPLEMENTED`.
- Versão-alvo: V1.
- Endpoints: `POST /api/v1/books/` e `PATCH /api/v1/books/{book_id}`.
- Entidade: `Book`.
- Testes: validação de URL, atualização, conflito e rollback.

Regra aprovada: durante o cadastro, um ISBN válido é consultado no Google Books.
Quando a fonte externa responde com título e autor válidos, esses metadados são
canônicos, preenchem o formulário em tempo de digitação e permanecem bloqueados.
O backend consulta novamente a fonte ao persistir e sobrescreve valores enviados
pelo cliente. O preenchimento manual só é aceito quando a consulta externa não
produz metadados mínimos.

- Estado: `IMPLEMENTED`.
- Versão-alvo: V1.
- Endpoints: `GET /api/v1/books/metadata/{isbn}` e `POST /api/v1/books/`.
- Entidades: `Book` e `Copy` inicial.
- Testes: preenchimento assíncrono, bloqueio dos campos, autoridade do backend e fallback manual.

Regra aprovada: toda obra nova deve ser persistida com um primeiro exemplar
ativo na mesma transação. A obra, o exemplar e seus registros de auditoria só
podem ser confirmados em conjunto; qualquer falha provoca rollback integral.
O status do exemplar inicial não integra o payload: o backend sempre o persiste
como `AVAILABLE` e força `is_active=true`.

Regra aprovada: o exemplar possui uma única destinação, armazenada no campo
obrigatório `copies.destination`. Os únicos valores permitidos são:

- `DIDACTIC`: exemplar destinado a empréstimo e sem preço de venda;
- `COMMERCIAL`: exemplar destinado a venda e com preço de venda obrigatório.

Não existe classificação, tag ou campo de destinação secundário.

| Estado | Significado |
|---|---|
| `AVAILABLE` | disponível para operação compatível |
| `BORROWED` | emprestado |
| `RESERVED` | reservado |
| `SOLD` | vendido e não reutilizável |
| `INACTIVE` | fora do acervo operacional |

As transições permitidas devem ser documentadas antes da implementação dos
services de circulação.

Regra aprovada: uma mesma obra pode possuir quantidades distintas de exemplares
para diferentes destinações de acervo dentro do mesmo cadastro. A quantidade é
representada pelos próprios registros individuais de `Copy`, e não por um campo
de quantidade na entidade.

A operação em lote permite cadastrar vários exemplares da mesma obra em uma
única transação, com destinações distintas entre os exemplares.

- Estado: `IMPLEMENTED`.
- Versão-alvo: V2.
- Endpoint: `POST /api/v1/copies/batch`.
- Entidades: `Book`, `Copy`.
- Ator autorizado: `SELLER`, `STOCK_KEEPER` ou `ADMINISTRATOR` (Issue #151).
- Cada exemplar deve possuir seu próprio `barcode`.
- A criação do lote é atômica: falha em qualquer exemplar provoca rollback
  integral da operação.
- Testes: lote com múltiplos exemplares, destinações distintas, lote vazio,
  obras diferentes no mesmo lote, erro de persistência e rollback.

## 10. Operações transacionais

Cada operação deve documentar:

- ator autorizado;
- pré-condições;
- alteração de estado;
- entidades afetadas;
- resultado de sucesso;
- erros possíveis;
- comportamento em concorrência;
- registro de auditoria.

(#29) Validação da situação do cliente

Status: `IMPLEMENTED`.

Versão-alvo: V2.

Endpoint: `GET /api/v1/clients/{client_id}/validation`.

Atores autorizados: `SELLER` e `ADMINISTRATOR`.

Pré-condições:
- o cliente deve existir;
- o usuário associado ao cliente deve estar ativo;
- o cliente não pode possuir empréstimo em aberto com devolução não registrada e
  data de vencimento ultrapassada.

Resultado de sucesso:
- HTTP 200;
- retorna `client_id` e `valid = true`.

Erros possíveis:

| Código | HTTP | Descrição |
|---|---:|---|
| `client_not_found` | 404 | Cliente não encontrado |
| `client_inactive` | 403 | Cliente inativo |
| `client_has_pending` | 409 | Cliente possui pendência ativa |
| `invalid_token` | 401 | Usuário não autenticado |

Concorrência:
- a consulta do cliente utiliza bloqueio transacional (`FOR UPDATE`);
- qualquer sincronização da penalização permanece na mesma transação.

Auditoria:
- caso a validação provoque alteração automática de `is_penalized`, a mudança é
  registrada no histórico de auditoria pelo mecanismo de controle de pendências.

### Empréstimo

Status: `IMPLEMENTED`.

Versão-alvo: V2.

Endpoint: `POST /api/v1/loans/`.

Entidades:
- `clients`;
- `copies`;
- `loans`;
- `employees`.

Atores autorizados:
- `SELLER`;
- `ADMINISTRATOR`.

#### Pré-condições

- o cliente deve existir;
- o usuário associado ao cliente deve estar ativo;
- o cliente não pode possuir pendências de empréstimos em atraso;
- o exemplar deve existir;
- o exemplar deve estar ativo;
- o exemplar deve possuir status `AVAILABLE`;
- o exemplar deve ser didático (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147); exemplar comercial é recusado com 409 `copy_not_for_loan`;
- atraso é decidido por data de negócio em America/Sao_Paulo (vencer hoje não é atraso), o mesmo predicado de `has_overdue_loan` (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147).

#### Registro

O empréstimo deve ser vinculado:
- ao cliente;
- ao exemplar;
- ao funcionário responsável pela operação.

O novo empréstimo é criado com:
- `status = OPEN`;
- `returned_at = NULL`.

O `employee_id` é obtido a partir do usuário autenticado.

#### Prazo de devolução

Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147: todo empréstimo (retirada V2 e empréstimo direto) vence um mês de calendário após o início efetivo do empréstimo, em America/Sao_Paulo, com o ajuste de fim de mês da V2 (o dia é limitado ao último dia do mês seguinte, ex.: 31/01 vence em 28/02 ou 29/02). O cálculo é único (`loan_due_at`, que reutiliza `next_month`). Substitui o prazo antigo de 15 dias corridos.

A `due_date` não é informada pelo cliente no momento da criação do empréstimo.

O backend calcula automaticamente:

- `loan_date`: momento do registro do empréstimo;
- `due_date`: um mês de calendário após `loan_date` (America/Sao_Paulo, mesmo horário).

Exemplos:
- empréstimo realizado em 02/10/2026;
- devolução prevista em 02/11/2026;
- empréstimo realizado em 31/01/2027; devolução prevista em 28/02/2027.

#### Concorrência e integridade

- o cliente é validado antes do registro;
- o exemplar é bloqueado transacionalmente durante a operação;
- um mesmo exemplar não pode possuir mais de um empréstimo com status `OPEN`;
- a validação do cliente e o registro do empréstimo participam da mesma transação;
- falha na operação provoca rollback;
- conflitos de integridade resultam em erro explícito.

#### Validação do cliente

A operação utiliza a validação da situação do cliente implementada em
`GET /api/v1/clients/{client_id}/validation`.

Além da validação disponibilizada pelo endpoint de consulta, o backend
revalida o cliente durante o registro do empréstimo.

#### Erros possíveis

| Código | HTTP | Descrição |
|---|---:|---|
| `client_not_found` | 404 | Cliente não encontrado |
| `client_inactive` | 403 | Cliente inativo |
| `client_has_pending` | 409 | Cliente possui pendência |
| — | 404 | Exemplar não encontrado ou inativo |
| — | 409 | Exemplar indisponível |
| `copy_not_for_loan` | 409 | Exemplar não é didático |
| — | 409 | Conflito ao registrar empréstimo |

#### Testes

- registro com cliente válido e exemplar disponível;
- cliente inativo;
- cliente com pendência;
- exemplar inexistente ou inativo;
- exemplar indisponível;
- erro de integridade;
- erro de banco e rollback;
- autorização por papel;
- integração do endpoint;
- cálculo automático da data prevista de devolução;
- validação de que `due_date` corresponde a um mês de calendário após `loan_date` em America/Sao_Paulo, inclusive em fim de mês;
- exemplar comercial recusado (`copy_not_for_loan`);
- atraso por data de negócio de São Paulo no empréstimo direto e na sincronização de penalidade do endpoint V1.

### Devolução

Status: `IMPLEMENTED`.

Versão-alvo: V2.

Endpoint: `PATCH /api/v1/loans/{loan_id}/return`.

Entidades:

- `loans`;
- `copies`.

Atores autorizados:

- `SELLER`;
- `ADMINISTRATOR`.

#### Pré-condições

- o empréstimo deve existir;
- o empréstimo deve possuir status `OPEN`;
- o exemplar vinculado ao empréstimo deve existir.

#### Registro

Ao registrar a devolução:

- `loans.returned_at` recebe automaticamente o momento da operação;
- `loans.status` é alterado para `RETURNED`;
- o exemplar vinculado ao empréstimo tem seu status alterado para `AVAILABLE`.

#### Concorrência e integridade

- o empréstimo é bloqueado transacionalmente durante a devolução;
- o exemplar vinculado também é bloqueado transacionalmente;
- não é permitida a devolução de um empréstimo que não esteja com status `OPEN`;
- a atualização do empréstimo e do exemplar participa da mesma transação;
- falha na operação provoca rollback;
- conflitos de integridade resultam em erro explícito.

#### Resultado de sucesso

- HTTP 200;
- empréstimo com status `RETURNED`;
- `returned_at` preenchido;
- exemplar novamente disponível para operação compatível.

#### Erros possíveis

| Situação | HTTP | Descrição |
|---|---:|---|
| Empréstimo não encontrado | 404 | Empréstimo informado não existe |
| Empréstimo não está aberto | 409 | Empréstimo não pode ser devolvido no estado atual |
| Exemplar não encontrado | 404 | Exemplar vinculado ao empréstimo não foi encontrado |
| Falha de integridade | 409 | Não foi possível concluir a devolução |
| Falha de banco | 500 | Não foi possível registrar a devolução |

#### Testes

- devolução de empréstimo aberto;
- preenchimento automático de `returned_at`;
- alteração do status para `RETURNED`;
- atualização do exemplar para `AVAILABLE`;
- empréstimo inexistente;
- tentativa de devolver empréstimo já encerrado;
- erro de banco e rollback;
- autorização do endpoint.

### Venda

Status da regra: `IMPLEMENTED`.

Versão-alvo: V2.

Endpoint: `POST /api/v1/sales/`.

Entidades:

- `sales`;
- `sale_items`;
- `clients`;
- `copies`;
- `employees`.

Atores autorizados:

- `SELLER`;
- `ADMINISTRATOR`.

#### Pré-condições

- o usuário deve estar autenticado;
- o usuário deve possuir papel autorizado para registrar a venda;
- os exemplares informados devem existir;
- os exemplares devem estar ativos;
- os exemplares devem estar com status `AVAILABLE`;
- quando um `client_id` for informado, o cliente deve existir.

#### Regra de destinação

- exemplares com destinação `DIDACTIC` não podem ser vendidos;
- a venda deve ser bloqueada antes da criação da venda e dos itens da venda;
- caso uma solicitação contenha exemplares de destinação `COMMERCIAL` e `DIDACTIC`, a operação inteira deve ser rejeitada;
- exemplares de destinação `COMMERCIAL` podem prosseguir para o registro da venda quando as demais pré-condições forem atendidas.

#### Registro

A venda é registrada:

- vinculada ao funcionário responsável;
- opcionalmente vinculada a um cliente;
- contendo um ou mais exemplares;
- com o preço unitário de cada item igual ao `sale_price` cadastrado no exemplar, lido do banco pelo backend;
- com `total_amount` calculado pelo backend a partir dos itens.

Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (decisão 3, implementada na Issue #149): a venda direta é paga no balcão e por isso é confirmada no ato. A venda é criada e confirmada na mesma transação (`status = CONFIRMED`) e cada exemplar passa a `SOLD`, pelo mesmo mecanismo da confirmação de venda V2 (gatilhos de banco `trg_validate_sale_transition` e `trg_apply_sale_copy_state`, que também registram o funcionário na auditoria); não há caminho paralelo. O valor `unit_price` enviado pelo cliente, se houver, é ignorado: o campo permanece opcional no schema apenas por compatibilidade e está descontinuado; o frontend não o envia.

O `employee_id` é obtido a partir do usuário autenticado.

#### Concorrência e integridade

- os exemplares são consultados com bloqueio transacional durante o registro;
- não é permitida a criação da venda para exemplar inexistente;
- não é permitida a criação da venda para exemplar inativo;
- não é permitida a criação da venda para exemplar que não esteja `AVAILABLE`;
- não é permitida a criação da venda para exemplar com destinação `DIDACTIC`;
- exemplar comercial sem `sale_price` é recusado com 409 `copy_without_price` (o banco já impede esse estado em exemplares comerciais; a recusa é uma defesa do service);
- o livro de cada exemplar é travado antes do exemplar (ordem livro → exemplar); duas vendas concorrentes do mesmo exemplar são serializadas: uma é confirmada e a outra recebe 409 de exemplar indisponível;
- a criação da venda, dos itens, a confirmação e a mudança do exemplar para `SOLD` ocorrem na mesma transação;
- falha na operação provoca rollback;
- conflitos de integridade resultam em erro explícito.

#### Resultado de sucesso

- HTTP 201;
- venda persistida;
- itens da venda persistidos com o preço cadastrado no exemplar;
- `total_amount` calculado pelo backend;
- `status = CONFIRMED`;
- exemplares com `status = SOLD`.

#### Erros possíveis

| Situação | HTTP | Descrição |
|---|---:|---|
| Cliente não encontrado | 404 | Cliente informado não existe |
| Exemplar não encontrado | 404 | Um ou mais exemplares informados não existem ou estão inativos |
| Exemplar indisponível | 409 | Um ou mais exemplares não estão disponíveis para venda |
| Exemplar didático | 409 | Exemplar com destinação `DIDACTIC` não pode ser vendido |
| Obra inativa | 409 | `book_inactive` |
| Exemplar comercial sem preço | 409 | `copy_without_price` |
| Falha de integridade | 409 | Não foi possível registrar a venda |
| Falha de banco | 500 | Não foi possível registrar a venda |

#### Testes

- registro de venda com sucesso, venda `CONFIRMED` e exemplar `SOLD`;
- registro com múltiplos exemplares;
- cálculo automático do `total_amount`;
- preço vindo do banco mesmo se outro valor for enviado;
- exemplar comercial sem preço recusado;
- concorrência de duas vendas do mesmo exemplar (uma vence, a outra recebe indisponível);
- auditoria do funcionário na mudança do exemplar;
- venda sem cliente;
- cliente inexistente;
- exemplar inexistente;
- exemplar inativo;
- exemplar indisponível;
- bloqueio de venda de exemplar `DIDACTIC`;
- bloqueio de venda quando uma operação contém exemplar `COMMERCIAL` e `DIDACTIC`;
- erro de integridade;
- erro de banco e rollback;
- autorização por papel;
- validação do contrato do endpoint.

#### Escopo ainda não implementado

Funcionalidade planejada (não implementada): estorno e cancelamento de venda. Uma venda confirmada é final no banco (`A confirmed sale is final and cannot be cancelled`) e nenhum endpoint a desfaz.

Dados anteriores: vendas `PENDING` criadas pelo fluxo direto antes da Issue #149 podem existir em bases já em uso. Elas mantêm o exemplar `AVAILABLE` e o impedem de nova venda (venda em andamento). Não há endpoint para confirmá-las ou cancelá-las e nenhuma migration de dados foi feita; o tratamento (confirmar ou cancelar caso a caso) fica como decisão operacional pendente do responsável.

### Reserva

Status: `PENDING`.

### Troca

Status: `OUT_OF_SCOPE` até existir definição formal.

## 11. Funcionários

- somente administrador pode cadastrar funcionário;
- funcionário deve ser persistido junto às entidades necessárias;
- papel informado deve existir;
- código deve ser único;
- falha parcial deve provocar rollback;
- resposta de sucesso só ocorre após persistência confirmada.

## 12. Auditoria

Devem ser auditadas as alterações de:

- obras;
- exemplares;
- empréstimos;
- vendas;
- reservas;
- permissões;
- funcionários.

O registro deve conter:

- funcionário;
- entidade;
- operação;
- valor anterior;
- novo valor;
- data/hora.

## 13. Regras pendentes

- obrigatoriedade de título e autor;
- checksum no cadastro de ISBN;
- ator de cada operação de circulação;
- política de reservas;
- confirmação e cancelamento de vendas;
- criação de funcionário e usuário na mesma transação;
- papéis oficiais da aplicação;
- pertencimento de cada fluxo à V1, V2 ou V3.
- atualização do estoque/status do exemplar após confirmação da venda;

## 14. Critérios de implementação

Uma regra só deve ser marcada como `IMPLEMENTED` quando houver:

- documentação aprovada;
- endpoint ou fluxo correspondente;
- service implementado;
- persistência funcional;
- autorização aplicada;
- testes de sucesso e erro;
- tratamento de concorrência, quando aplicável.

## 15. Inativação de Usuário

Status: `IMPLEMENTED`
Versão-alvo: v1
Endpoint: `PATCH /api/v1/users/{id}/inactivate`
Entidades: `users`, `user_sessions`

### Ator autorizado

- `ADMINISTRATOR`

### Pré-condições

- O executor deve estar autenticado com papel `ADMINISTRATOR`.
- O usuário-alvo deve existir.
- O usuário-alvo deve estar ativo (`is_active = true`).
- O administrador não pode inativar a si mesmo.

### Alteração de estado

- `users.is_active` é definido como `false`.
- `users.updated_at` é atualizado com o momento da operação.
- Todas as sessões ativas do usuário-alvo são revogadas (`user_sessions.revoked_at`) na mesma transação.

### Resultado de sucesso

HTTP 200 com o estado atualizado do usuário (`id`, `name`, `email`, `is_active`, `updated_at`).

### Erros possíveis

| Código | HTTP | Descrição |
|---|---|---|
| `user_not_found` | 404 | Usuário-alvo não existe |
| `user_already_inactive` | 409 | Usuário-alvo já está inativo |
| `user_self_inactivation` | 422 | Administrador tentou inativar a si mesmo |
| `permission_denied` | 403 | Executor não possui papel `ADMINISTRATOR` |
| `invalid_token` | 401 | Token ausente ou inválido |

### Efeito colateral de autenticação

- Login (`POST /auth/login`) com usuário inativo retorna `invalid_credentials` (HTTP 401) sem vazar o motivo real.
- Qualquer rota protegida acessada com token de usuário inativo retorna `user_inactive` (HTTP 403).

### Atomicidade

A revogação de sessões e a inativação do usuário ocorrem na mesma transação. Falha em qualquer etapa causa rollback completo.

### Testes esperados

- sucesso com mudança de status;
- recurso inexistente (404);
- já inativo (409);
- auto-inativação (422);
- sem autorização (401 e 403);
- bloqueio de login com conta inativa;
- bloqueio de rota protegida com token de conta inativa;
- repository não controla transação;
- atomicidade da operação (ordem: revoke → inactivate → commit).

## 16. Gestão administrativa de usuários

Status: `IMPLEMENTED`
Versão-alvo: v1
Endpoints: `GET /api/v1/users`, `GET /api/v1/users/{id}` e `PATCH /api/v1/users/{id}`
Entidades: `users`, `profiles`, `clients`, `employees`, `roles`, `user_roles`

- Somente `ADMINISTRATOR` ativo pode listar, consultar e editar usuários.
- A listagem inclui contas ativas e inativas e pode ser filtrada por um dos
  quatro papéis oficiais: `USER`, `SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR`.
- O cadastro administrativo recebe exatamente um papel inicial.
- A resposta administrativa nunca expõe senha, hash, tokens ou sessões.
- Nome, e-mail e papel funcional podem ser alterados; a mudança de papel
  mantém `user_roles` e o registro `clients` ou `employees` consistentes na
  mesma transação.
- Não é permitido remover o próprio papel administrativo.
- Não é permitido remover nem inativar o último administrador ativo. A
  verificação é serializada por lock transacional no papel `ADMINISTRATOR`.
- E-mail permanece único e é armazenado normalizado em minúsculas.
- A tela de cadastro existente em `/gestao/funcionarios` é reutilizada para os
  quatro papéis oficiais; `USER` cria `Client`, e papéis internos criam
  `Employee`.

### Exclusão definitiva

Status: `PENDING`

A exclusão física de usuários não pertence ao contrato implementado. Até serem
definidos os impactos sobre histórico, auditoria e referências de circulação,
a interface não oferece a ação (referência da Issue #131) e a inativação é a
alternativa, na tela de edição do usuário. Não existe endpoint `DELETE` para usuários.

## 17. Referência UX para a V2

Estado: `APPROVED` para a direção visual solicitada; funcionalidades de circulação permanecem `PENDING` até definição dos contratos e implementação.

- Versão-alvo: V2.
- Referência: Figma LibStock — UX V2, incluindo a seção de complementos.
- Home e login usam fundo branco e cabeçalho verde escuro; componentes compartilhados apresentam dados reais da API.
- A referência descreve reserva de compra e bloqueio de venda de exemplares didáticos. Estes requisitos ainda não equivalem a endpoints implementados.
- Prazo de devolução, prazo/expiração da reserva e política de pendências não são inferidos de datas ilustrativas.
- A proposta de empréstimo direto no balcão exige validação, conforme anotação do próprio Figma.
- Matriz de implementação, limitações e validação: [V2_IMPLEMENTATION.md](V2_IMPLEMENTATION.md).

## 18. V2 — detalhes e solicitações do cliente

Estado: `APPROVED` para o recorte inicial solicitado em 03/10/2026; as alterações de acompanhamento da seção 19 substituem os limites abaixo. Implementação e
validação detalhadas em `V2_IMPLEMENTATION.md`.

- A busca global apresenta resultados na home; cada card abre `/livros/:id`.
- Detalhes são públicos e respeitam a visibilidade vigente do catálogo.
- `GET /api/v1/catalog/books/{id}` retorna disponibilidade por modalidade:
  empréstimo, venda e consulta local. O frontend não a deduz do gênero.
- Empréstimo conta exemplares didáticos ativos e `AVAILABLE`; venda conta
  comerciais ativos e `AVAILABLE`. Exemplares em vendas pendentes/confirmadas
  são excluídos. Somente o backend decide a elegibilidade.
- Consulta local permanece explicitamente não configurada, conforme confirmação
  do usuário; a disponibilidade é `null`, sem simular uma quantidade.
- `POST /api/v1/loan-requests` e `POST /api/v1/purchase-requests` exigem papel
  `USER`, usuário/perfil ativo, registro de cliente e ausência de penalidade.
  O cliente é obtido da autenticação, nunca do corpo da requisição.
- A data pretendida de retirada deve ser hoje ou posterior, no calendário de
  `America/Sao_Paulo`. O prazo do empréstimo é um mês de calendário, limitado ao
  último dia do próximo mês quando necessário (31/01 → 28/02, ou 29/02 em ano
  bissexto). O backend calcula a devolução; o frontend mostra uma prévia somente leitura.
- Uma solicitação fica `PENDING`, vinculada à obra, ao cliente e à data de
  retirada. Não equivale à retirada ou à venda concluída. Não altera o estado
  físico, não retém exemplar e não garante disponibilidade futura.
- Existe no máximo uma solicitação pendente por cliente/obra em cada modalidade;
  empréstimo e compra possuem unicidade independente.
- A criação verifica disponibilidade atual, trava cliente/obra/exemplar durante
  a transação e persiste somente após validar os requisitos. Conflitos de
  duplicidade são protegidos por índices únicos; falhas provocam rollback.
- Uma solicitação de compra exige exemplar comercial disponível. Didáticos
  nunca habilitam essa solicitação. A compra é finalizada no balcão; a tela
  orienta o cliente a informar seu e-mail cadastrado na retirada.
- A auditoria de criação é registrada no banco na mesma transação, identificando
  o cliente em `new_value.client_id`; não há funcionário fictício.
- O snackbar de sucesso só aparece após resposta de persistência da API.

### Limites deste recorte

Estado: `PENDING` para atendimento/retirada pelo funcionário, cancelamento,
expiração, histórico visual, fila/prioridade, retenção de exemplares, registro
efetivo de empréstimo/venda e reserva de compra de exemplares indisponíveis.
`purchase_requests` registra a intenção de retirada de exemplar disponível;
`purchase_reservations` continua sendo a estrutura futura da fila de compra
de exemplares indisponíveis. Não se alteram os triggers existentes dessa fila.

## 19. V2 — acompanhamento e integridade da circulação

Estado: `APPROVED` conforme o fluxo de acompanhamento solicitado em 03/10/2026.

- As consultas do cliente usam o usuário autenticado; não recebem identidade, estado ou posição de fila do frontend.
- Somente solicitações de empréstimo sem retirada confirmada e empréstimos OPEN aparecem em Meus empréstimos. Retirada e devolução são exclusivas de SELLER/ADMINISTRATOR com cadastro de funcionário ativo.
- O empréstimo efetivo começa na retirada real. A devolução é um mês de calendário após essa retirada; a data da solicitação é uma prévia.
- O `due_date` exibido na solicitação de empréstimo é apenas uma estimativa até a retirada; o prazo real é calculado na confirmação da retirada, um mês de calendário após a retirada efetiva (Issue #148).
- Atraso significa que a data de negócio em America/Sao_Paulo ultrapassou a data de devolução nesse mesmo calendário. A data de vencimento ainda não conta como atraso.
- Cliente com usuário/perfil inativo, penalidade cadastrada ou empréstimo OPEN em atraso não pode solicitar empréstimo, solicitar compra, entrar na fila ou concluir retirada/compra. A devolução continua permitida para regularizar o exemplar.
- Compra usa o domínio existente PurchaseReservation: WAITING, NOTIFIED, FULFILLED, CANCELLED e EXPIRED (ciclo completo abaixo). NOTIFIED é o estado interno de disponibilidade para retirada; não significa envio de notificação V3.
- Solicitação de compra disponível é vinculada a uma reserva NOTIFIED com exemplar comercial. A intenção da data de retirada fica em PurchaseRequest; os estados operacionais pertencem à reserva, sem um segundo ciclo de estados.
- A fila usa a ordem persistida no backend. A posição exibida conta somente WAITING anteriores da mesma obra, inclusive de clientes inelegíveis. Destinar um exemplar atende a primeira reserva WAITING elegível; novas solicitações de compra não podem passar essa fila.
- Somente exemplares comerciais ativos podem atender compras. Exemplares destinados são excluídos da disponibilidade pública e protegidos de empréstimo, inativação, conversão, troca de obra e venda a outro cliente, inclusive no banco.
- Destinação ao cliente mantém o status físico AVAILABLE; uma venda confirmada aplica SOLD e conclui a reserva de forma atômica. Uma falha mantém o exemplar e a reserva anteriores.
- A auditoria de transições registra o funcionário que executou a operação. A devolução por outro funcionário não atribui a auditoria ao responsável pela retirada original.
- Minhas reservas inclui somente WAITING/NOTIFIED; compras concluídas não aparecem. Meus empréstimos e Minhas reservas possuem mensagens explícitas para listas vazias.

Reservas de compra — ciclo completo (Issue #150). Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #150):

- Estados: `WAITING` (aguardando), `NOTIFIED` (exemplar destinado, aguardando retirada), `FULFILLED` (venda confirmada), `CANCELLED` e `EXPIRED`. `FULFILLED`, `CANCELLED` e `EXPIRED` são finais.
- Prazo de retirada: ao destinar um exemplar (`POST /api/v1/staff/books/{id}/allocate-purchase`), `expires_at` é o último instante (23:59:59.999) do 5º dia corrido, no fuso America/Sao_Paulo, contado a partir da data de negócio da destinação. Fórmula (`reservation_pickup_deadline` em `core/business_dates.py`): `data_negócio(destinação em America/Sao_Paulo) + 5 dias, às 23:59:59.999`. Exemplo: destinação em 03/10 vence em 08/10 às 23:59:59.999; destinação às 23:30 de 03/10 em São Paulo (02:30 UTC de 04/10) também vence em 08/10. A reserva vence quando `expires_at` é estritamente anterior ao instante atual. Reserva que nasce `NOTIFIED` com exemplar destinado (`POST /api/v1/purchase-requests` com exemplar livre) também é uma destinação: recebe o mesmo prazo, calculado a partir da data de negócio da criação, e expira pelas mesmas regras. Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #150). `POST /api/v1/purchase-reservations` com exemplar livre e sem fila `WAITING` continua recusado (409 `purchase_available`); só cria reserva `WAITING` (ver precedência da fila abaixo).
- Expiração (preguiçosa e determinística): uma reserva `NOTIFIED` com `expires_at` vencido passa a `EXPIRED`, e o exemplar volta a ficar livre, porque o exemplar só é retido enquanto a reserva está `NOTIFIED` (índice único parcial e gatilhos continuam válidos; `allocated_copy_id` é preservado como histórico). A gravação ocorre dentro da transação das operações de escrita da obra, depois de travar o livro: destinação (`allocate-purchase`), venda (`confirm-sale`), cancelamento, nova reserva (`POST /purchase-reservations`) e nova solicitação de compra da mesma obra, e no endpoint explícito `POST /api/v1/staff/purchase-reservations/expire` (SELLER/ADMINISTRATOR), que expira todas as vencidas obra a obra. Consultas (`GET /staff/purchase-reservations`, `GET /purchase-reservations/me`) não gravam: apenas sinalizam `expired` e, no balcão, contam o exemplar como liberável para `can_allocate`. Quando uma operação de escrita recusa a reserva por vencimento (`confirm-sale` com `reservation_expired`, cancelamento com `reservation_not_cancellable`), a expiração é efetivada (commit) mesmo assim. A auditoria da expiração registra o funcionário que executou a operação que a efetivou. Não há rotina agendada.
- Cancelamento: o cliente cancela a própria reserva `WAITING` ou `NOTIFIED` (`POST /api/v1/purchase-reservations/{id}/cancel`, papel USER; reserva de outro cliente responde 404 `reservation_not_found`). `SELLER` e `ADMINISTRATOR` com cadastro de funcionário ativo cancelam qualquer reserva (`POST /api/v1/staff/purchase-reservations/{id}/cancel`, corpo opcional `{reason}` de até 255 caracteres). O status vira `CANCELLED` e o exemplar destinado é liberado na mesma transação. Estado final responde 409 `reservation_not_cancellable` com `details.status`. Auditoria: o gatilho de transição registra o `UPDATE` e um registro explícito `CANCEL` em `audit_logs` com `actor_user_id`, `actor_role` (`USER` ou `STAFF`) e `reason`; `employee_id` só é preenchido para funcionário (cliente não possui cadastro de funcionário).
- Destinação para a primeira reserva elegível: `allocate-purchase` percorre as reservas `WAITING` da obra na ordem da fila (`queue_position`, `id`) e destina o exemplar livre à primeira cujo cliente é elegível (mesmo predicado de `client_eligibility.py`, com o cliente travado). Reservas de clientes inelegíveis continuam `WAITING` e mantêm a posição (a posição exibida conta todas as `WAITING` anteriores, elegíveis ou não). Se nenhuma reserva tiver cliente elegível: 409 `no_eligible_reservation`, sem alteração; sem reserva aguardando: 404 `reservation_not_found`; sem exemplar livre: 409 `purchase_unavailable`. Isto substitui a regra anterior de que o primeiro cliente inelegível bloqueava a destinação.
- Data de retirada da solicitação de compra (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147, Issue #150): quando a solicitação nasce destinada (`NOTIFIED`, exemplar livre e sem fila `WAITING`), `pickup_date` não pode ultrapassar a data do prazo de retirada calculado no instante da criação (`reservation_pickup_deadline(agora).date()`, hoje + 5 dias em America/Sao_Paulo). Acima disso: 422 `pickup_date_after_deadline`, nada é gravado. O backend não expõe o limite; o frontend calcula o mesmo valor (`pickupDeadline` em `loan-dates.ts`: data de negócio de hoje + 5 dias) para o `max` do campo e a mensagem. Solicitação que entra na fila (`WAITING`) não tem prazo ainda e aceita a data informada.
- Backfill do prazo (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147, Issue #150): a migration `20261003_0014` preenche `expires_at` das reservas `NOTIFIED` sem prazo com `reservation_pickup_deadline(notified_at)` (SQL: `((notified_at AT TIME ZONE 'America/Sao_Paulo')::date + 6)::timestamp AT TIME ZONE 'America/Sao_Paulo' - interval '1 millisecond'`), desabilitando só durante o UPDATE o gatilho de validação (cliente hoje penalizado/inativo não pode impedir o preenchimento); a auditoria continua ativa, sem funcionário. O downgrade não desfaz os valores (decisão mais segura: são válidos pela regra, o código anterior os tolera e não há marca que os distinga de prazos gravados pela aplicação).
- Venda direta de exemplar destinado (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147, Issue #150): `POST /api/v1/sales/` trava os livros, expira as reservas vencidas de cada obra (livro, depois reservas, depois exemplares) e recusa com 409 `copy_reserved` o exemplar ainda destinado a reserva `NOTIFIED` no prazo (qualquer cliente; a venda ao cliente reservado é o `confirm-sale`), nunca 500 do gatilho `guard_allocated_sale_item`. Reserva vencida é expirada na própria venda, que prossegue.
- Inativação de obra (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147, Issue #150): após travar o livro e antes de travar exemplares e contar operações, as reservas `NOTIFIED` vencidas da obra são expiradas; só reservas `WAITING` ou `NOTIFIED` no prazo bloqueiam (`book_has_active_operations`).
- Precedência da fila (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147, Issue #150): havendo reserva `WAITING` na obra, uma nova solicitação de compra (`POST /api/v1/purchase-requests`) ou reserva (`POST /api/v1/purchase-reservations`) entra no fim da fila (`WAITING`), mesmo com exemplar comercial livre, sem destinação imediata; a resposta da solicitação traz `reservation_status` (`NOTIFIED` ou `WAITING`). Isso substitui o 409 `purchase_queue_pending` e, para a reserva, o 409 `purchase_available` quando já há fila. Sem fila `WAITING`, o comportamento anterior continua (destinação imediata; reserva com exemplar livre recusada). Exige ao menos um exemplar comercial ativo não vendido (senão 409 `purchase_unavailable` / `reservation_unavailable`). A migration `20261003_0015` (reversível; a 0012 não foi alterada) ajusta o gatilho de validação para aceitar `WAITING` com exemplar livre quando já existe outra `WAITING` na obra.
- Ordem de locks: livro, reserva(s), cliente(s), exemplar. Todas as operações são atômicas.
- Códigos de erro estáveis: `reservation_not_found` (404), `reservation_not_ready`, `reservation_expired`, `reservation_not_cancellable`, `no_eligible_reservation`, `purchase_unavailable`, `pickup_date_after_deadline` (422), `copy_reserved`, `client_ineligible`, `client_required` (403) e `circulation_persistence_error` (500).
- Decisão pendente: notificação ao cliente e expiração agendada (V3); hoje a expiração é efetivada nas operações de escrita ou no endpoint explícito.

Limitação técnica: a solicitação de empréstimo não retém exemplar. A disponibilidade é revalidada na retirada. Consulta local continua não configurada por decisão expressa do usuário.

Rastreabilidade e pendências para os devs: [V2_REVIEW.md](V2_REVIEW.md).

## 20. Controle de pendências e penalização de clientes

Status: `IMPLEMENTED`
Versão: V2

Endpoints:
- `GET /api/v1/clients/{id}/pendencies`
- `PATCH /api/v1/clients/{id}/penalty`

Entidades:
- `clients`
- `loans`
- `copies`
- `books`
- `audit_logs`

### Pendência

Um cliente possui pendência quando possui pelo menos um empréstimo que satisfaça simultaneamente:

- `status = OPEN`;
- `returned_at IS NULL`;
- `due_date` anterior ao início do dia de negócio atual em America/Sao_Paulo (Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147; vencer hoje não é atraso). A sincronização de penalidade do `GET /api/v1/clients/{id}/pendencies` usa o mesmo predicado de `has_overdue_loan`, deixando de usar o instante `now()`.

Transição (Issue #148): ao passar a usar o corte por data de negócio, a sincronização V1 retira penalidades que a regra antiga por instante havia criado (por exemplo, empréstimo vencido no próprio dia), registrando a remoção em `audit_logs`. Os fluxos V2 leem o `is_penalized` gravado; por isso a divergência fica restrita ao dia da implantação, sem reconciliação automática.

A pendência é derivada do estado do empréstimo e não é armazenada em uma tabela própria.

### Penalização

Quando existe pelo menos uma pendência:

- `clients.is_penalized = true`.

Quando não existe mais nenhuma pendência:

- `clients.is_penalized = false`.

A penalização é sincronizada automaticamente pelo backend nas consultas de pendências e nas operações relevantes que utilizarem o serviço de sincronização. O empréstimo, devolução e reserva ainda não estão integrados. Esses três podem consumir o synchronize_penalty().

### Aplicação e remoção manual

`SELLER` e `ADMINISTRATOR` podem solicitar aplicação ou remoção manual da
penalização.

A aplicação manual exige pelo menos uma pendência ativa.

A remoção manual somente é aceita quando não existem pendências ativas.

O motivo é obrigatório para ambas as operações.

### Histórico

Toda mudança efetiva de penalização gera um registro imutável em `audit_logs`
contendo:

- ação;
- estado anterior;
- novo estado;
- motivo;
- responsável;
- data/hora.

Ações automáticas utilizam `actor_type = SYSTEM` e não possuem
`employee_id`.

Ações realizadas por funcionários utilizam `actor_type = EMPLOYEE` e
registram o `employee_id`.

### Atomicidade

A alteração de `clients.is_penalized` e seu histórico devem ocorrer na mesma transação.

### Concorrência

A sincronização utiliza lock transacional sobre o cliente para serializar alterações concorrentes da sua situação de penalização.

### Integração com circulação

Operações de circulação que dependam da aptidão do cliente devem reavaliar as pendências antes de prosseguir.

O fluxo de empréstimo utiliza a validação da situação do cliente antes do registro da operação.

O serviço de consulta e sincronização de penalização permanece preparado para ser consumido por outros fluxos de circulação.

A reserva ainda não está integrada ao controle de pendências.

## 21. V2 — balcão operacional (Issue #122)

Estado: `APPROVED` para o recorte de telas e consultas solicitado em 03/10/2026; reutiliza as regras da seção 19 sem alterá-las.

- Regra aprovada: a área de balcão é restrita a funcionário ativo com papel `SELLER` ou `ADMINISTRATOR`, no frontend (guards) e no backend (papéis e cadastro de funcionário ativo). `STOCK_KEEPER` e `USER` não acessam.
- Regra aprovada: as quatro operações (confirmar retirada, devolução, destinar exemplar e confirmar venda) usam apenas os POST V2 de `/api/v1/staff`. Os endpoints transacionais antigos (`/api/v1/loans`, `/api/v1/sales`) não são usados por essas quatro operações; a única exceção é o registro da venda direta (Issue #126), descrito abaixo.
- Regra aprovada: a interface exige seleção na lista (sem digitar IDs), confirmação explícita antes de cada alteração, bloqueio de envio duplicado e só mostra sucesso após resposta 2xx do backend; após qualquer resposta a lista é recarregada.
- Regra aprovada: consultas de balcão são somente leitura e expõem apenas os dados necessários (nome, e-mail, situação de elegibilidade, obra, exemplar, datas).
- Regra aprovada: os exemplares oferecidos para retirada e a contagem de comerciais livres usam a mesma definição de exemplar livre da confirmação (disponibilidade comum), incluindo exclusão de exemplares destinados e com venda em andamento.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #150): a destinação vai para a primeira reserva elegível da fila e clientes inelegíveis permanecem na fila sem perder a posição (substitui a regra anterior que bloqueava a destinação quando o primeiro da fila era inelegível). Em `GET /api/v1/staff/purchase-reservations`, `can_allocate` é verdadeiro somente para a primeira reserva `WAITING` elegível da obra, com obra ativa e exemplar livre (ou liberável por vencimento); caso contrário `allocation_blocked_reason` é `BOOK_INACTIVE`, `CLIENT_INELIGIBLE` (a própria reserva tem cliente inelegível), `NOT_FIRST_ELIGIBLE` (há elegível à frente) ou `NO_FREE_COPY`. A tela explica o bloqueio e destina apenas pela reserva elegível.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #150): o balcão exibe "Retirar até dd/MM/yyyy" (data do `expires_at` em America/Sao_Paulo), "Prazo encerrado em" quando `expired`, "Cancelar reserva de X" com confirmação (`POST /staff/purchase-reservations/{id}/cancel`) em cada reserva em andamento e "Liberar exemplares vencidos" (`POST /staff/purchase-reservations/expire`) quando alguma reserva está vencida e ainda não gravada. Sucesso só após 2xx, envio duplo bloqueado, recusas (`reservation_not_cancellable`, `no_eligible_reservation`) no snackbar e a lista é recarregada.
- Limitação técnica: as consultas retornam no máximo `limit` itens (até 100), sem paginação; a tela avisa quando o limite é atingido. A posição na fila é calculada por reserva na consulta.
- Regra aprovada: a consulta de pendências do balcão é `GET /api/v1/staff/clients/{id}/pendencies`, somente leitura, com atraso pela regra V2 (calendário de America/Sao_Paulo) e sem sincronizar penalidade.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147: o endpoint V1 `GET /api/v1/clients/{id}/pendencies` sincroniza a penalização com o mesmo atraso por data de negócio de São Paulo da V2 (mesmo predicado de `has_overdue_loan`). Continua sincronizando a penalização e não exigindo funcionário ativo (comportamento herdado). O balcão não o utiliza.
- Regra aprovada (indicadores do Painel): `GET /api/v1/staff/dashboard`, somente leitura, mesmo guard de `/staff`. Definições exatas: empréstimos ativos = empréstimos `OPEN`; devoluções hoje = empréstimos com `returned_at` na data atual de America/Sao_Paulo (00:00 inclusive a 00:00 seguinte exclusive); reservas aguardando = reservas de compra `WAITING`; pendências = clientes distintos com empréstimo `OPEN` em atraso pela regra V2 (vencimento antes do início do dia de negócio atual; vencer hoje não é atraso). O cálculo de atraso é o mesmo de `has_overdue_loan`, compartilhado no repository.
- Escopo (03/10/2026): o empréstimo direto (`POST /api/v1/loans`) e a venda direta (`POST /api/v1/sales`) coexistem com os fluxos V2 sob a decisão do responsável de entrega incremental. Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147: o empréstimo direto segue o prazo de um mês de calendário e o atraso por data de São Paulo da V2 (seção Empréstimo), e a venda direta é confirmada no ato com o preço cadastrado no exemplar (Issue #149, ver Venda direta no balcão abaixo). A venda direta foi implementada no balcão (Issue #126, abaixo) e o empréstimo direto também (Issue #136, abaixo).
- Regra aprovada (Acervo do balcão, Issue #124): as consultas `GET /api/v1/staff/books`, `GET /api/v1/staff/books/{id}` e `GET /api/v1/staff/copies` são somente leitura e usam o guard de `/staff` (`SELLER`/`ADMINISTRATOR`). A obra informa total e contagem por destinação apenas de exemplares ativos e não vendidos; o detalhe lista os exemplares com destinação, status e as situações `free` (livre pela definição comum) e `allocated_for_purchase`. A tela deriva o rótulo do exemplar desses fatos (Disponível, Emprestado, Reservado para venda, Venda em andamento, Vendido, Inativo).
- Regra aprovada (Acervo do balcão): categoria, inativação e reativação de obra usam `PATCH /api/v1/books/{id}`, autorizado no backend a `SELLER`, `STOCK_KEEPER`, `MANAGER` e `ADMINISTRATOR` (decisão delegada de 2026-10-03, Issue #147/#151; antes da Issue #151 `SELLER` só lia). A tela mostra as ações a esses papéis (no balcão chegam `SELLER` e `ADMINISTRATOR`), exige confirmação, bloqueia envio duplicado, anuncia sucesso só após 2xx e recarrega a obra após qualquer resposta. Categoria vazia é enviada como nula.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (decisão 7, Issue #151, reativação de obra): `PATCH /api/v1/books/{id}` com `is_active=true` numa obra inativa só é aceito se existir ao menos um exemplar ativo; senão, 409 `book_without_active_copy` e nada é alterado (rollback), nunca 500. O service trava o livro e seus exemplares (`FOR UPDATE`, o mesmo padrão da inativação) antes de conferir. O gatilho adiado `trg_active_book_has_copy` (obra ativa exige exemplar ativo) continua sendo a última barreira: se ele rejeitar o commit, o resultado também é 409 `book_without_active_copy`. Reativar uma obra já ativa ou alterar outros campos de obra ativa não faz a conferência. Reativar não reativa exemplares nem desfaz operações; o histórico é preservado. Na tela, "Reativar obra" aparece no cartão "Situação da obra" (obra inativa; `SELLER`, `STOCK_KEEPER`, `MANAGER`, `ADMINISTRATOR`), pede confirmação ("Reativar <obra>?" e "Confirmar reativação"), é antecipado como desabilitado quando nenhum exemplar carregado está ativo, bloqueia envio duplicado e só anuncia sucesso após 2xx.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (decisão 8, Issue #151, edição e conversão de exemplar): `PATCH /api/v1/copies/{id}` (`SELLER`, `STOCK_KEEPER`, `ADMINISTRATOR` com cadastro de funcionário ativo) altera `destination`, `condition`, `sale_price` e `acquired_at`; só os campos enviados mudam e pelo menos um é obrigatório. O código (`barcode`), a obra, o status e `is_active` são imutáveis por esta operação: campo desconhecido, inclusive `barcode`, é 422. Só é permitida para exemplar `AVAILABLE`, ativo, sem destinação a reserva de compra (`purchase_reservations.allocated_copy_id` com status `NOTIFIED`) e sem venda em andamento (item de venda em venda `PENDING`); empréstimo aberto torna o exemplar `BORROWED` e venda confirmada o torna `SOLD`, ambos recusados por `copy_not_available`. Conversão para `COMMERCIAL` exige `sale_price` maior que zero (se o exemplar já era comercial, vale o preço atual quando não enviado); conversão para `DIDACTIC` remove o preço (`sale_price` é gravado como nulo) e informar preço para exemplar didático é erro. Respeita `chk_commercial_price` e `chk_didactic_without_sale_price`. Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (conversão e solicitações de retirada, Issue #151): converter para `COMMERCIAL` o último exemplar didático livre (didático, ativo, disponível, sem venda em andamento e não destinado) de uma obra que tenha solicitação de retirada pendente (`loan_requests.loan_id IS NULL`) é recusado com 409 `copy_needed_for_requests`, avaliado dentro do lock livro → exemplar; havendo outro didático livre, ou nenhuma solicitação pendente, a conversão é permitida, e as demais edições do exemplar não são afetadas. Erros: 404 `copy_not_found`; 409 com `code` do primeiro motivo, na ordem `copy_inactive`, `copy_not_available`, `copy_allocated`, `copy_in_operation` e `details.reasons[]` com todos (e 409 `copy_needed_for_requests` pela regra acima); 422 `copy_sale_price_required`, 422 `copy_sale_price_not_allowed` (preço para exemplar didático sem conversão) e 422 de contrato (`destination` e `sale_price` incoerentes, campo desconhecido, corpo vazio, preço negativo, condição acima de 30 caracteres); 403 `employee_record_required`; 500 `copy_update_persistence_error` com rollback. A operação é atômica: o service trava o livro e depois o exemplar (`FOR UPDATE`), reavalia as condições e grava na mesma transação, serializando com empréstimo, venda e destinação concorrentes (um empréstimo ou venda já confirmado vence a edição, e uma conversão confirmada faz o empréstimo ser recusado por `copy_not_for_loan`). Se o gatilho `trg_guard_allocated_copy_change` ou as constraints barrarem algo não previsto, o resultado é 409 ou 422, nunca 500. Auditoria: `trg_audit_copies` registra o `UPDATE` com o funcionário responsável (`set_config('libstock.employee_id')`) e os valores antigo e novo. Os erros de gatilho do banco são mapeados pelo SQLSTATE, não pelo texto: `LS001` (troca de destinação sem papel `SELLER`, `STOCK_KEEPER` ou `ADMINISTRATOR` do funcionário responsável, resultando em 403 `permission_denied`) e `LS002` (exemplar fora de `AVAILABLE`/`INACTIVE`, resultando em 409 `copy_not_available`); os gatilhos já integrados sem SQLSTATE próprio (`trg_guard_allocated_copy_change`, `trg_active_book_has_copy`) são reconhecidos pela mensagem primária exata e as constraints `chk_commercial_price` e `chk_didactic_without_sale_price` pelo nome. Em `PATCH /api/v1/books/{id}`, quando `is_active` é enviado, o service trava a obra e os exemplares antes de decidir entre inativar e reativar, usando o valor travado. Migration `20261003_0014`: o gatilho `guard_copy_integrity` só aceitava `ADMINISTRATOR` para trocar a destinação (migration 0007); passou a aceitar `SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR`, e continua recusando troca sem funcionário responsável ou de exemplar que não esteja `AVAILABLE`/`INACTIVE`. A "destinação da obra" não existe no modelo (a destinação é por exemplar, com um único valor). Na tela: botão "Editar" por exemplar (desabilitado com o motivo quando o status já indica bloqueio) abre o painel "Editando exemplar #código" com código somente leitura, finalidade (Empréstimo/Venda), preço de venda (só para Venda, vírgula ou ponto), condição (até 30 caracteres) e "Salvar exemplar", com confirmação que mostra o antes e o depois, sucesso só após 2xx, envio duplicado bloqueado e erros de domínio no snackbar. A data de aquisição é aceita pela API, mas a tela não a mostra, pois o detalhe do balcão não a devolve.
- Decisão pendente: exibição de preço no detalhe do acervo. A referência diz que nenhum preço foi definido na V2, mas existe `sale_price` por exemplar comercial; a tela não exibe preço.
- Limitação técnica: a busca de obras e exemplares usa também o ISBN sem hífens e o filtro de `GET /api/v1/staff/loans` passou a aceitar ISBN; o resultado é limitado por `limit` (padrão 50) e a tela avisa quando o limite é atingido.
- Regra aprovada (Empréstimos ativos e devolução no balcão, Issue #125): `/balcao/emprestimos/ativos` é uma tabela somente leitura de `GET /api/v1/staff/loans`, com atraso pela regra V2 já existente (sem regra nova); o contador "ativos • atrasados" conta os itens listados, e a tela avisa quando o limite de `limit` é atingido. `/balcao/devolucoes` localiza o empréstimo aberto por `q` (código do exemplar ou ISBN, que o backend também aceita com hífens) e registra a devolução por `POST /api/v1/staff/loans/{id}/confirm-return` com confirmação, bloqueio de envio duplicado e sucesso só após 2xx; depois de qualquer resposta a busca é refeita. Nenhuma consulta nova no backend. A frase do rodapé ("Atraso gera pendência do cliente até a devolução ser registrada") reflete a seção 20 e a seção 21 (pendência = empréstimo `OPEN` em atraso) e não cria multa nem penalidade.
- Limitação técnica: o campo de devolução usa o mesmo `q` da lista de empréstimos, que também casa nome do cliente, e-mail, título e autor; a interface rotula o campo como código do exemplar ou ISBN, mas não restringe a consulta. Um ISBN pode retornar vários empréstimos abertos da mesma obra; o funcionário escolhe o exemplar correto.
- Decisão pendente: "Fila desta obra" nas solicitações (item do Figma sem regra ou desenho aprovado neste recorte) segue fora da interface. O comprovante de devolução foi aprovado e implementado (Issue #152, abaixo). O item "Reservas" da sidebar foi entregue na Issue #127 (abaixo).
- Divergências da referência (Issue #151, `png telas/recortes/funcionario_08.png` e `funcionario_09.png`): o painel "Editando exemplar" aparece abaixo da lista de exemplares, não ao lado, e a lista traz "Editar" e "Excluir exemplar" por linha em vez de "Selecionar"; o campo "Status" do desenho não existe (o status resulta das operações e não é editável); o texto "Nenhum preço foi definido na V2" não se aplica, pois o preço é do exemplar; o painel acrescenta preço de venda (obrigatório para Venda) e condição; o rádio "Didático/Comercial" da obra (funcionario_08) segue sem existir, porque a destinação é por exemplar; "Reativar obra" não tem tela de referência e foi desenhado com o mesmo padrão de confirmação da inativação.
- Regra aprovada (Venda direta no balcão, Issue #126; atualizada pela Issue #149): `/balcao/vendas` busca o exemplar por código, ISBN ou título (`GET /api/v1/staff/copies`; a elegibilidade `sellable` e o motivo do bloqueio vêm do backend) e registra a venda por `POST /api/v1/sales/`, restrito a `SELLER` e `ADMINISTRATOR` (sem ampliação de papéis), sem cliente (`client_id` opcional) e com um item. A tela pede confirmação, bloqueia envio duplicado e só mostra sucesso após 2xx. Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (decisão 3): a venda direta é confirmada no ato (pagamento no balcão), o exemplar passa a `SOLD` na mesma transação e o preço de cada item é sempre o `sale_price` cadastrado no exemplar, definido pelo servidor, que ignora o `unit_price` enviado; exemplar comercial sem preço é recusado com 409 `copy_without_price`. A tela envia apenas o exemplar, diz "Venda registrada" com a obra, o exemplar vendido, o total e o número da venda devolvidos pelo backend, e depois refaz a busca (o exemplar passa a aparecer como indisponível). Exemplar didático é bloqueado no cartão e, se o POST for tentado, vale o erro de domínio existente (409, "Exemplares didáticos não podem ser vendidos."); obra inativa recebe 409 `book_inactive`. Nenhuma migration nova.
- Funcionalidade planejada (Refs #126, #149): estorno e cancelamento de venda confirmada; não há endpoint nem regra aprovada. O comprovante de venda existe (Issue #152, abaixo). A tela ainda não exibe estoque antes e depois (o backend não os devolve).
- Decisão pendente (Refs #126): venda para cliente identificado (o endpoint aceita `client_id`, a referência não o mostra). A validação do preço e a duplicidade de venda do mesmo exemplar foram resolvidas na Issue #149: o preço vem sempre do exemplar e duas vendas concorrentes do mesmo exemplar são serializadas pelo lock livro → exemplar (uma vence, a outra recebe 409).
- Regra aprovada (rotas do balcão, Issue #126): as reservas de compra foram movidas de `/balcao/vendas` para `/balcao/reservas` sem alteração funcional, para liberar `/balcao/vendas` à venda direta. O item de menu "Reservas" e o redesenho foram entregues na Issue #127 (abaixo); o atalho "Reservas" em Clientes continua levando a `/balcao/reservas`.
- Regra aprovada (Reservas de compra no balcão, Issue #127): item "Reservas" na sidebar (após "Vendas") e rotas `/balcao/reservas` (fila por obra) e `/balcao/reservas/:id?cliente=` (atender, confirmar e venda concluída), sem endpoint, regra ou migration novos. A lista usa `GET /api/v1/staff/purchase-reservations` (busca por título, nome, e-mail ou código do exemplar; filtro de cliente vindo de "Clientes") e agrupa por obra no frontend; a posição exibida é a `queue_position` do backend (só reservas aguardando). A destinação usa `POST /api/v1/staff/books/{id}/allocate-purchase` com diálogo de confirmação (apenas a primeira reserva elegível da fila; o bloqueio é explicado).
- Regra aprovada (Atender reserva): a tela localiza a reserva na mesma consulta (filtrada pelo cliente da URL; não há consulta por id), mostra cliente, situação de elegibilidade, exemplar destinado e `expires_at` somente se persistido, e exige que o código digitado seja igual (após remover espaços nas pontas) ao `allocated_copy_barcode` devolvido pelo backend antes de avançar. A etapa de resumo confirma a venda por `POST /api/v1/staff/purchase-reservations/{id}/confirm-sale`, bloqueia envio duplicado e só mostra "Venda da reserva concluída" após 2xx. O texto "exemplar ficará Vendido e a reserva será concluída" reflete o gatilho de banco já existente (venda confirmada → exemplar `SOLD`, reserva `FULFILLED`, coberto em `test_staff_desk_postgres`). Erros de domínio (`reservation_expired`, `reservation_not_ready`, `client_ineligible` etc.) são exibidos com a mensagem do backend, sem sucesso, e a reserva é recarregada.
- Regra aprovada (estados de recuperação): "Nenhuma reserva encontrada" aparece quando uma busca ou o filtro de cliente não retorna reservas (com "Limpar busca"); sem filtro, a tela diz que não há reservas em andamento. "Reserva fora do prazo" aparece somente quando o backend informa `expired` (`expires_at` persistido já vencido); a tela não calcula nem inventa prazo, não oferece venda e leva a "Consultar fila".
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #150): a política de prazo de retirada (5 dias corridos, `expires_at` na destinação), cancelamento e expiração (`EXPIRED`) foi aprovada e implementada; ver seção 19. Permanece pendente (Refs #127) apenas o rótulo "Status: consultar situação atualizada da reserva" e "Origem: reserva de compra · prioridade ativa" das referências, sem dado equivalente.
- Divergências da referência (Issue #127): o bloco "Estoque comercial disponível: 1 → 0" não é exibido (o backend não devolve estoque antes/depois); "Fulano passa à 1ª posição" só aparece se uma nova consulta pós-venda retornar a próxima reserva aguardando da obra; a ordinal "1ª" da reserva com exemplar destinado não é exibida porque `queue_position` só existe para reservas aguardando; "Consultar outra obra" apenas foca o campo de busca; "Registrar outra venda" leva à venda direta (`/balcao/vendas`); a conferência do exemplar é por digitação do código (sem seletor de exemplares).
- Limitação técnica (Issue #127): a reserva em "Atender" é achada na lista limitada a 50 itens; sem filtro de cliente na URL e com mais de 50 reservas ativas ela pode não aparecer (a tela informa que ela não está mais em andamento). Sem endpoint de detalhe por id.
- Regra aprovada (Controle de pendências no balcão, Issue #128): `/balcao/clientes` ("Controle de pendências") busca clientes por nome ou e-mail (`GET /api/v1/staff/clients`, mínimo de 2 caracteres) e consulta `GET /api/v1/staff/clients/{id}/pendencies`, somente leitura, com atraso pela regra V2 e sem sincronizar penalidade. Resultado único é consultado automaticamente; vários resultados são listados para escolha. O cartão mostra "Pendência ativa" com obra, exemplar, vencimento e dias de atraso de cada empréstimo em atraso, ou "Sem pendência"; avisos de penalizado e cadastro inativo vêm de `is_penalized`/`is_active`. A frase "Pendência = empréstimo não devolvido após a data prevista" reflete a seção 20 (empréstimo `OPEN` em atraso). Os atalhos Solicitações, Empréstimos ativos e Reservas guardam o cliente como filtro das respectivas telas. Nenhum endpoint, regra ou migration novos.
- Limitação técnica (Issue #128): busca por CPF. O modelo de cliente não possui CPF, portanto a referência "Nome, CPF ou e-mail" é atendida apenas por nome ou e-mail e a tela não menciona CPF.
- Divergências da referência (Issue #128): o cartão exibe também e-mail, avisos de penalização/inativo e os atalhos; "Exemplar #00127" mostra o código real do exemplar; a lista de escolha para múltiplos resultados e o estado "Sem pendência" não existem no desenho. A frase "Enquanto ativa, novas operações que exigem cliente apto devem ser bloqueadas" segue a seção 20 (operações de circulação reavaliam pendências), mas o bloqueio é do backend, não desta tela.
- Decisão pendente (Refs #128): listar mais de 100 empréstimos em atraso de um cliente (limite interno da consulta) e gestão manual de penalidade na interface. A divergência de atraso entre o V1 e o V2 foi resolvida pela unificação (Issue #148).
- Regra aprovada (Inclusão de exemplar no balcão, Issue #135): `/balcao/acervo/:id/exemplares/novo` usa o endpoint existente `POST /api/v1/copies/` (`SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR`, conforme a decisão delegada de 2026-10-03, Issue #147/#151; antes disso `SELLER` não via o botão "Novo exemplar"; `STOCK_KEEPER` não acessa `/balcao`). Campos enviados: obra, código (obrigatório, até 100 caracteres), finalidade (Empréstimo = `DIDACTIC`, Venda = `COMMERCIAL`) e preço de venda, obrigatório para Venda e proibido para Empréstimo (validação do backend replicada na tela). O status inicial é definido pelo backend (`AVAILABLE`). Obra inativa não aceita exemplar (404 do backend; a tela não oferece o formulário). Sucesso só após 2xx; a nova quantidade vem da recarga da obra. Envio duplicado é bloqueado.
- Regra aprovada (código duplicado): o backend responde 409 em violação de unicidade do código; a tela mantém os dados, marca o código como já cadastrado, informa que nenhum exemplar foi incluído e libera o envio ao trocar o código.
- Limitação técnica (Issue #135): `POST /api/v1/copies/` devolve o 409 como `HTTPException` com mensagem e sem o código estável `duplicate_barcode` (existente apenas no cadastro de obra). A tela reconhece o 409 do endpoint como código duplicado; qualquer outra violação de integridade também retornaria 409 com a mesma mensagem.
- Divergências da referência (Issue #135, inclusão): o formulário tem o campo "Preço de venda" quando a finalidade é Venda, exigido pelo backend e ausente do desenho; condição e data de aquisição, aceitas pelo backend, não aparecem no desenho e não são enviadas; a quantidade "de 4 para 5" usa o total real da obra antes e depois; "Ver exemplares" volta aos detalhes da obra.
- Regra aprovada (Inativação de obra, Issue #135): usa `PATCH /api/v1/books/{id}` com `is_active=false`. O modal "Inativar <obra>?" mostra a "Situação verificada" lida dos exemplares carregados (quantidade vinculada, exemplares emprestados ou reservados para venda) e exige "Confirmar inativação" (o backend bloqueia a inativação enquanto houver operação em andamento, regra abaixo); após 2xx a tela exibe "<obra> foi inativada. O histórico foi preservado." e o cartão "Situação da obra" (inativa, exemplares vinculados, indisponível) com "Voltar ao acervo".
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03 (Issue #135, inativação de obra bloqueada): `PATCH /api/v1/books/{id}` com `is_active=false` é bloqueado enquanto houver operação em andamento: empréstimo `OPEN` de qualquer exemplar da obra, solicitação de retirada pendente (`loan_id IS NULL`) da obra ou reserva de compra `WAITING` ou `NOTIFIED` (aguardando ou com exemplar destinado) da obra. A validação fica no service, que trava o livro e os exemplares da obra (`FOR UPDATE`, o mesmo padrão dos fluxos de circulação) antes de contar, e só vale quando `is_active` passa de verdadeiro para falso; as demais alterações da obra não são afetadas. O bloqueio responde 409 `book_has_active_operations` com `details.counts` (`open_loans`, `pending_loan_requests`, `purchase_reservations`) e `details.links` (até 10 por tipo: `type`, `copy_barcode` e `client_name`; o nome do cliente só é devolvido a quem tem `ADMINISTRATOR` ou `SELLER`, e os demais papéis recebem apenas tipo, código do exemplar e contagens), e nada é alterado (rollback). Exemplares e empréstimos permanecem intactos. A reativação é regra aprovada na Issue #151 (abaixo). Antes desta regra, nenhum serviço, trigger ou constraint bloqueava a inativação (a única trava, `trg_active_book_has_copy`, exige exemplar ativo só para obra ativa).
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03 (Issue #135, exclusão de exemplar): `DELETE /api/v1/copies/{id}`, restrito a `SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR` com cadastro de funcionário ativo (a Issue #151 incluiu o `SELLER`, que antes recebia 403; `USER` recebe 403, sem token 401, usuário ou funcionário inativo 403). A exclusão é física e só é permitida se o exemplar estiver `AVAILABLE` e sem histórico: nenhum empréstimo (aberto ou encerrado), nenhum item de venda, nenhuma reserva de compra que o referencie (`allocated_copy_id` ou `fulfilled_copy_id`) e nenhuma solicitação vinculada (de retirada, via empréstimo; de compra, via reserva). Também é bloqueada se for o último exemplar ativo de uma obra ativa. Bloqueio: 409 com `code` do primeiro motivo encontrado, na ordem `copy_not_available`, `copy_has_history`, `last_active_copy`, `details.reasons[]` (todos os motivos, com `code` e `message`) e `details.history` (`loans`, `sales`, `purchase_reservations`, `requests`). Exemplar inexistente: 404 `copy_not_found`; funcionário sem cadastro ativo: 403 `employee_record_required`; sucesso: 200 `{id, book_id, barcode, deleted}`. A operação é atômica: o service trava o livro e depois o exemplar (`FOR UPDATE`), reavalia as condições e exclui na mesma transação, serializando com empréstimo, venda e destinação concorrentes; se o exemplar sumir durante a espera, 404. Se a FK `RESTRICT` do banco ou o gatilho adiado `trg_copy_keeps_active_book_valid` barrar algo não previsto, o resultado é bloqueio (`copy_has_history` ou `last_active_copy`), nunca 500; falha de persistência desconhecida é 500 `copy_delete_persistence_error` com rollback. Auditoria: o `trg_audit_copies` registra o `DELETE` com o funcionário responsável (`set_config('libstock.employee_id')`) e o valor antigo do exemplar. Nenhuma migration foi necessária.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03 (Issue #135, obra inativa em empréstimo e venda diretos): `POST /api/v1/loans/` e `POST /api/v1/sales/` travam o livro do exemplar antes do exemplar (ordem livro → exemplar, a mesma da inativação e dos fluxos V2; na venda, vários livros em ordem de id) e recusam obra inativa com 409 `book_inactive`, sem gravar. Assim, uma inativação em andamento serializa com esses registros: quem pega o lock primeiro define o resultado. A validação de destinação continua como estava: a venda já bloqueia exemplar didático; para o empréstimo não há regra aprovada de exigir exemplar didático (ver Issue #136), então nada foi inventado.
- Divergências da referência (Issue #135, exclusão e bloqueio): os estados "Exclusão bloqueada", "Inativação bloqueada" e "Exemplar excluído" aparecem na própria página de detalhes da obra (cartão de bloqueio e mensagem de sucesso), não em telas separadas; o bloqueio de exemplar lista os motivos e contagens de histórico devolvidos pelo backend, sem cliente e data de devolução (o 409 não os retorna); "Consultar empréstimo" não existe, o bloqueio de exemplar tem "Voltar aos exemplares" e o de obra tem "Consultar empréstimos" (`/balcao/emprestimos/ativos`) e "Consultar reservas" (`/balcao/reservas`); o botão "Excluir exemplar" aparece em cada linha (só para papéis autorizados) e é antecipado como desabilitado, com o motivo, quando o status já indica bloqueio (não disponível, reservado para venda ou último exemplar ativo), mas a decisão final é do backend; o painel "Editando exemplar" foi entregue na Issue #151 (abaixo); "Quantidade da obra após exclusão: 5 → 4" usa o total real carregado.
- Regra aprovada (Empréstimo direto no balcão, Issue #136; proposta condicional EAP 1.2.9–1.2.13, incluída por decisão do responsável de entrega incremental): `/balcao/emprestimos/novo` (acessível pelo card "Novo empréstimo" de Empréstimos/Início e pelo card "Empréstimo" do Painel) escolhe o cliente por `GET /api/v1/staff/clients` (nome ou e-mail, mínimo de 2 caracteres) e o exemplar por `GET /api/v1/staff/copies` (código, ISBN ou título), revisa e registra por `POST /api/v1/loans/`, endpoint existente restrito a `SELLER` e `ADMINISTRATOR` (sem ampliação de papéis; `SELLER` pode registrar). O corpo contém apenas `client_id` e `copy_id`. A tela pede confirmação explícita, bloqueia envio duplicado e só mostra "Empréstimo registrado" após 2xx. Nenhum endpoint, regra, consulta ou migration novos.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (prazo no empréstimo direto, Issue #148): o prazo é calculado pelo backend e é de um mês de calendário (seção Empréstimo). A tela não calcula o prazo antes do registro ("calculada automaticamente ao registrar", com a nota "um mês de calendário") e, depois de 2xx, exibe `loan_date` e `due_date` retornados, no calendário de America/Sao_Paulo.
- Regra aprovada (elegibilidade antecipada, sem regra nova): o cliente selecionado com `eligible=false` (conta inativa, penalizado ou empréstimo em atraso pela regra V2) bloqueia a revisão e mostra os motivos; o exemplar só é oferecido quando é didático, livre (mesma definição de exemplar livre da retirada V2, que exclui destinados e com venda em andamento) e de obra ativa, o mesmo critério dos exemplares elegíveis da retirada. Exemplares comerciais, emprestados, reservados, vendidos, inativos ou de obra inativa aparecem desabilitados com o motivo. É uma antecipação de leitura: a decisão final é do backend.
- Regra aprovada (empréstimo bloqueado): o estado "Empréstimo bloqueado" vem dos erros de domínio reais de `POST /api/v1/loans/` e usa a mensagem do backend: `client_not_found` (404), `client_inactive` (403) e `client_has_pending` (409) levam ao bloqueio de cliente ("Consultar pendências", "Selecionar outro cliente"); 404 (exemplar não encontrado ou inativo) e 409 (exemplar indisponível ou conflito de integridade) levam ao bloqueio de exemplar ("Atualizar seleção", que refaz a busca). Falhas inesperadas (por exemplo 500 ou rede) mantêm a revisão com a mensagem e sem sucesso, orientando a conferir os empréstimos ativos antes de repetir. Nenhum sucesso é exibido sem 2xx.
- Divergências da referência (Issue #136): o comprovante foi aprovado depois (Issue #152): a tela de sucesso exibe o comprovante com "Imprimir comprovante" no lugar de "Baixar comprovante" (não há arquivo para baixar nem e-mail), sem a frase "O comprovante estará disponível"; o campo "Buscar por nome, CPF ou e-mail" aceita apenas nome ou e-mail (o modelo de cliente não tem CPF, Issue #128); "Retirada: hoje" usa a data de negócio de America/Sao_Paulo e, no registro, a `loan_date` do backend; "Devolução prevista" vem de `due_date` do backend; "Status do exemplar: Emprestado" só é exibido se a resposta traz o empréstimo `OPEN`, que o gatilho `trg_apply_loan_copy_state` converte em exemplar `BORROWED`; busca de cliente e de exemplar por botão em vez de lista suspensa; "Novo empréstimo" no final volta ao formulário vazio e há o link "Ver empréstimos ativos". Notas para desenvolvedores das referências não são interface.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #148): `POST /api/v1/loans/` aceita somente exemplar didático (além de disponível, ativo, de obra ativa e cliente apto); exemplar comercial é recusado com 409 `copy_not_for_loan`, e a tela mostra a mensagem do backend. Os 409 de exemplar indisponível e de conflito de integridade não têm código estável (`HTTPException`), e a tela os distingue pelo status HTTP. Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147: o gatilho `trg_link_client_loan_request` vincula ao novo empréstimo a solicitação de empréstimo pendente do mesmo cliente e da mesma obra, se existir; esse efeito colateral é regra aprovada e permanece como está.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #152, decisão 9): comprovante digital de empréstimo, devolução e venda, exibido na tela e imprimível, gerado somente a partir dos dados persistidos e reimprimível por consulta somente leitura. Sem e-mail nesta versão (o canal e-mail segue fora do escopo). Endpoints (`/api/v1/receipts`, nenhuma escrita, nenhuma migration):
  - `GET /api/v1/receipts/loans/{id}`: nº do empréstimo, cliente (nome e matrícula, se houver), obra, exemplar (código de barras), data do empréstimo, vencimento e funcionário responsável. Empréstimo `CANCELLED` não tem comprovante (404).
  - `GET /api/v1/receipts/returns/{loan_id}`: os dados do empréstimo mais `returned_at` e `days_late`, calculado pela regra V2 (datas de negócio de America/Sao_Paulo; vencer ou devolver no dia do vencimento não é atraso). Só existe com `returned_at` gravado; empréstimo ainda aberto responde 409 `loan_not_returned`. Não há multa, valor ou penalidade no comprovante.
  - `GET /api/v1/receipts/sales/{id}`: nº da venda, data, cliente (ou venda sem cliente), funcionário, itens com obra, exemplar e preço unitário gravado, e total. Somente venda `CONFIRMED`; `PENDING`, `CANCELLED` e inexistente respondem 404.
  - Autorização: `SELLER` ou `ADMINISTRATOR` com cadastro de funcionário ativo (senão 403 `employee_record_required`) leem qualquer comprovante; `USER` lê somente os próprios (cliente do empréstimo ou da venda). Comprovante alheio, de venda sem cliente ou inexistente responde o mesmo 404 `receipt_not_found`, sem revelar existência. Sem token: 401; outros papéis: 403; identificador inválido: 422.
  - Interface: componente compartilhado `app-receipt` com botão "Imprimir comprovante" (`window.print()`, CSS `@media print` que imprime só o comprovante, sem dependência nova). É exibido depois do 2xx da retirada (`confirm-pickup`), do empréstimo direto, da devolução, da venda direta e da venda de reserva (`confirm-sale`), sempre consultando o backend com o identificador devolvido (não monta o comprovante a partir da resposta da operação). Rotas dedicadas, com guard de sessão e papéis `USER`, `SELLER` e `ADMINISTRATOR`: `/comprovantes/emprestimo/:id`, `/comprovantes/devolucao/:id` e `/comprovantes/venda/:id`; servem à reimpressão no balcão e no totem. Em "Meus empréstimos" o cliente reimprime o comprovante de empréstimos ativos e em atraso ("Ver comprovante").
  - Lacuna (limitação técnica): "Meus empréstimos" lista apenas solicitações aguardando retirada e empréstimos abertos; não há listagem de empréstimos encerrados nem de compras do cliente, então o cliente alcança comprovantes de devolução e de venda somente pelo link direto da rota dedicada. O funcionário reimprime por número. Listagem de histórico fica como funcionalidade planejada, sem regra aprovada.
- Fora do escopo: e-mail de comprovante, notificações e gestão manual de penalidade pela interface (o cancelamento de reservas foi entregue na Issue #150).
- Regra aprovada (Feedback por snackbar e estados de recuperação, Issue #137): componente compartilhado `app-snackbar` com as quatro variantes da referência (sucesso, erro, atenção, informação), hospedado uma única vez no layout do balcão e descartado ao sair dele. Erros usam região `role="alert"` (assertiva); as demais, `role="status"` (educada); as duas regiões existem desde o início para o anúncio funcionar, o foco nunca é movido, há botão "Fechar" e Esc fecha quando o foco está na mensagem. Sucesso e informação sem ação somem após 8 s; erro, atenção e mensagens com ação ficam até o fechamento (a referência não indica tempo; os 8 s são decisão de implementação). Orientação da referência aplicada: sucesso e erro de uma ação vão para o snackbar; bloqueios e decisões (cartões de bloqueio, "Operação bloqueada", tela de venda/empréstimo concluído, fora do prazo) continuam como estado, sem repetir a mesma mensagem no snackbar; confirmação destrutiva continua em diálogo modal.
- Regra aprovada (feedback nas operações de escrita do balcão, Issue #137): sucesso só após 2xx, com os textos já existentes por operação (retirada, devolução, destinação, categoria, inativação, exclusão de exemplar). Recusa de domínio 4xx usa a mensagem do backend: 409 como atenção e as demais como erro. Falha de rede (status 0) ou 5xx mostra o estado "Não foi possível salvar" (referência 07_2: "A operação não foi concluída… Atualize a consulta antes de repetir a operação para evitar registros duplicados") com "Atualizar consulta" e "Voltar", sem snackbar. A tela nunca reenvia sozinha; como o resultado pode ser incerto, a nova tentativa é manual, depois de atualizar a consulta (a lista é recarregada após qualquer resposta) e novo diálogo de confirmação. Não há idempotência no backend, por isso não existe botão "Tentar novamente" que reenvie a escrita.
- Divergências da referência (Issue #137): os textos prontos da referência ("Devolução registrada com sucesso.", "Venda registrada com sucesso." etc.) não são usados porque as mensagens atuais descrevem o comportamento real (por exemplo, a venda direta usa "Venda registrada" com os dados devolvidos pelo backend, e não o texto genérico); a variante informação existe no componente, mas nenhuma tela do balcão a usa ainda (a posição na fila é exibida em cartões); a tela de atendimento de reserva, a de inclusão de exemplar e o empréstimo direto mostram o sucesso em estado próprio (referências 02, 03 e 06) e por isso não disparam snackbar; as falhas de carregamento (consultas GET) seguem em alerta com "Tentar novamente", que é seguro por ser leitura.

- Regra aprovada (telas do cliente: login, início e categoria, Issue #129): usam somente os endpoints públicos de leitura `/api/v1/catalog/*` (`featured-books`, `genres`, `books`, `genres/{slug}/books`) e a autenticação existente; nenhuma regra de negócio nova. A disponibilidade nos cartões vem do contrato do catálogo: "Empréstimo disponível" (destinação didática livre), "Venda disponível" (comercial livre) e "Esgotado" (sem exemplar livre, US02). A consulta local permanece não configurada.
- Regra aprovada (busca dentro da categoria, Issue #129): `GET /api/v1/catalog/genres/{slug}/books` aceita o parâmetro opcional `q` (até 100 caracteres), somente leitura e público, que filtra por trecho do título ou do autor (sem diferenciar maiúsculas; `%` e `_` são literais) dentro da categoria, mantendo a paginação e a regra de visibilidade do catálogo (obra ativa com exemplar ativo). Termo em branco equivale a sem filtro. Não altera resposta, schemas nem autorização.
- Divergências da referência (Issue #129): (1) filtrar por duas categorias ao mesmo tempo não existe no backend (lacuna; os chips navegam uma categoria por vez); (2) o chip "Mais", "Todos", "Ver todos" e "Explorar acervo" foram atendidos pela Issue #153 (ver regra abaixo); (3) o início continua listando as categorias em destaque, e "Mais" as substitui pela lista completa; (4) o texto "Indisponível" da referência aparece como "Esgotado" (US02/contrato do catálogo); (5) "Ver todos" nos destaques leva ao acervo completo (Issue #153); (6) o campo de busca global não oferece "gênero" como critério (a busca pública aceita título, autor, ISBN e código de barras); (7) o início mantém o bloco recolhível "Buscar por título, autor, ISBN ou código de barras", que não consta da referência; (8) o login mantém "Esqueceu a senha?" desabilitado com "em breve", sem fluxo de recuperação (decisão pendente, fora do escopo, nota "DEV" da referência não é interface). Imagens e dados das referências são ilustrativos.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #153, decisão 11): consultas somente leitura para a experiência do cliente e do totem. (1) `GET /api/v1/catalog/genres?all=true` (público) devolve todas as categorias, em ordem alfabética, inclusive as fora de destaque; sem `all` (ou `all=false`) mantém só as em destaque. É a lista do chip "Mais". (2) `GET /api/v1/catalog/books/all?page=&page_size=&q=` (público) lista o acervo completo, paginado (`page` ≥ 1, `page_size` de 1 a 48, padrão 12), ordenado por título e id, com `q` opcional (até 100 caracteres) filtrando por trecho do título ou do autor; só obras ativas com ao menos um exemplar ativo, com as mesmas ofertas e a mesma disponibilidade do catálogo (resposta `{items, total, page, page_size}`). A rota do frontend é `/acervo` ("Ver todos", "Todos", "Explorar acervo" e "Explorar livros"); página e busca ficam na URL. (3) `GET /api/v1/me/eligibility` (papel `USER`, identidade vem da sessão) devolve `{eligible, reasons[]}`, com `reasons` de código `inactive` (perfil ou usuário inativo), `penalized` (penalidade registrada) e `overdue_loan` (empréstimo em aberto vencido pela regra V2, data de negócio de America/Sao_Paulo), cada um com `message`; usa o mesmo `is_client_eligible`/`has_overdue_loan` das escritas, é somente leitura, não bloqueia linhas e NÃO sincroniza penalidade. Sem sessão 401; papel diferente de `USER` 403; usuário sem cadastro de cliente 403 `client_required`. A decisão final continua no envio (`client_ineligible`). O frontend mostra "Situação do cliente: apto — conta ativa e sem pendências" (ou "inapto" com os motivos, desabilitando "Confirmar reserva") na confirmação da reserva de compra e usa os motivos no cartão de bloqueio; as solicitações de empréstimo e de compra não têm etapa de confirmação própria e seguem decididas pelo backend no envio. Se a consulta falhar, a tela avisa e não impede o envio.
- Regra aprovada (Gestão de usuários do administrador, Issue #131): usa os endpoints existentes `GET /api/v1/users`, `GET /api/v1/users/{id}`, `PATCH /api/v1/users/{id}` e `PATCH /api/v1/users/{id}/inactivate` (seções 15 e 16), sem backend novo. A inativação é pedida na tela de edição, com cartão de confirmação ("Inativar usuário?"), e só é anunciada como concluída após 2xx; erros de domínio (`user_self_inactivation`, último administrador, etc.) usam a mensagem do backend. A alteração de perfil também pede confirmação antes do `PATCH`. A listagem oferece Ver e Editar (somente Ver para inativos), com busca local por nome ou e-mail.
- Regra aprovada (Pendências no detalhe do usuário, Issue #131): seção somente leitura, exibida apenas para usuários com perfil `USER`, que consulta `GET /api/v1/staff/clients/{id}/pendencies` (regra V2, sem sincronizar penalidade; `ADMINISTRATOR` já tem acesso). O id do cliente é o id do usuário. Não usa `GET /api/v1/clients/{id}/pendencies` (V1, sincroniza penalidade). Nenhuma ação de penalidade manual é exposta: a referência não a mostra, embora `PATCH /api/v1/clients/{id}/penalty` exista e esteja aprovado na seção 20.
- Regra aprovada (Acesso por navegação, Issue #131): o menu lateral do balcão exibe "Usuários" somente para `ADMINISTRATOR`, apontando para `/gestao/usuarios`. É conveniência de interface; a autorização continua no backend e nos guards das rotas.
- Limitação técnica (Issue #131): CPF não existe no modelo de dados; o campo CPF do detalhe e o termo "CPF" da busca da referência não foram implementados. A busca por nome ou e-mail é feita no frontend sobre a lista retornada, pois `GET /api/v1/users` filtra apenas por perfil.
- Divergências da referência (Issue #131): detalhe e edição seguem em duas rotas (a referência as combina); a página de usuários não aparece dentro do layout do balcão; a listagem não tem mais o botão Inativar nem o Excluir desabilitado (a exclusão definitiva continua pendente, seção 16); perfis exibidos com os quatro rótulos oficiais; usuário inativo só pode ser consultado (a edição de inativos não consta da referência).

## Política operacional de promoção de release — Issues #113 e #120

- Status: `APPROVED` — promoção por PR, aprovação automática e merge normal
  com preservação dos commits originais autorizados pelo usuário em 2026-10-03; substitui a promoção direta
  anterior. Não altera regras do domínio da API.
- Regra aprovada: após disparo manual, abrir PR de `integracao` para `main`,
  aguardar a CI existente, aprovar com identidade diferente do autor do PR e
  solicitar auto-merge com merge commit, sem rebase ou squash. Respeitar proteções sem bypass.
- Regra aprovada: calcular a versão pela maior tag remota estável
  `vMAJOR.MINOR.PATCH` e escolha `patch` (padrão), `minor` ou `major`, zerando
  componentes inferiores. Sem tags estáveis, usar `v0.0.0` como base.
- Regra aprovada: somente após o merge de um PR de promoção, publicar tag no
  SHA resultante daquele PR e criar a GitHub Release com notas automáticas.
  Não criar commit adicional para a versão ou alterar versões de pacotes/API.
  PR fechado sem merge não publica Release. Não sobrescrever tags existentes.
- Regra aprovada: Render e Vercel continuam usando o merge em `main` via suas
  integrações Git existentes, sem deploy adicional na criação da Release.
- Limitação técnica: aprovação automática exige permissão da GitHub App para
  PRs e configuração de aprovação por Actions; auto-merge/merge commits precisam estar
  habilitados. Exigências de Code Owners ou outras proteções podem exigir
  ação humana. Conflitos não são resolvidos nem ignorados automaticamente.
- Limitação técnica: merge, tag e criação de Release não são atômicos. Uma
  falha da API após o merge deve ser corrigida repetindo o job de publicação.
  Tags já publicadas são reutilizadas apenas se apontarem para o SHA correto.
- Limitação técnica: `integracao` não é reescrita pelo workflow. O merge preserva
  os SHAs e autores originais e adiciona somente o commit de merge do PR.
- Testes esperados: escolhas de versão, metadados de PR, origem interna,
  SHA integrado, colisão de tag, autorização, falha da API e repetição segura.

Detalhes e condições de operação em [RELEASE.md](RELEASE.md).

## Compatibilidade após integração com a main — PR #118

Estado: `PENDING` para unificação dos contratos de circulação.

- Os endpoints diretos de empréstimo/venda/pendências recebidos da main permanecem disponíveis, junto aos endpoints de confirmação das solicitações V2.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #148): o empréstimo direto (`LoanService`) e a confirmação da solicitação V2 (`CirculationService`) usam o mesmo prazo de um mês de calendário (`loan_due_at`).
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #148): o serviço de pendências V1 e o acompanhamento V2 usam o mesmo atraso por data de negócio de America/Sao_Paulo (predicado compartilhado com `has_overdue_loan`).
- A home mantém a disponibilidade por modalidade e os links para detalhes da V2. O contrato administrativo de consulta de disponibilidade e o cadastro de exemplares foram preservados.

- Regra aprovada (telas do cliente: detalhes, reservas e empréstimos, Issue #130): usam apenas os endpoints existentes (`GET /catalog/books/{id}`, `POST /loan-requests`, `POST /purchase-requests`, `POST /purchase-reservations`, `GET /loans/me`, `GET /purchase-reservations/me`) sem alterar o backend. A reserva de compra é precedida de confirmação na tela e só é considerada registrada após 2xx; a posição exibida é a devolvida pela API. Erros de domínio mostram a mensagem do backend (`client_ineligible`, `loan_request_duplicate`, `purchase_request_duplicate`, `reservation_duplicate`, `loan_unavailable`, `purchase_unavailable`, `reservation_unavailable`, `purchase_available`). No bloqueio `client_ineligible` a tela lê `GET /loans/me` apenas para listar empréstimos em atraso do cliente autenticado.
- Divergências da referência (Issue #130): "Retire até <data>" aparece quando a reserva destinada tem `expires_at` (prazo real de 5 dias corridos desde a Issue #150; seção 19). Regra aprovada — decisão delegada pelo responsável em 2026-10-03, Issue #147 (Issue #150): Minhas reservas oferece "Cancelar reserva" (aguardando ou destinada, com confirmação, envio duplo bloqueado, sucesso só após 2xx, snackbar) e, quando `expired`, informa o encerramento do prazo sem oferecer cancelamento. "Situação do cliente: apto — conta ativa e sem pendências" é exibida na confirmação da reserva a partir de `GET /api/v1/me/eligibility` (Issue #153), que também informa a penalidade sem atraso; a consulta local permanece não configurada, sem texto de regra. Imagens e dados são ilustrativos.
