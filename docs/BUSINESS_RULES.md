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
- vendas: registro da venda e bloqueio de venda de exemplares didáticos implementados; confirmação da venda, atualização do status do exemplar e demais etapas do fluxo ainda dependem de regras específicas.

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
| `SELLER` | atendimento e operações de balcão quando os endpoints estiverem implementados |
| `STOCK_KEEPER` | cadastrar obras e operar acervo, se autorizado |
| `ADMINISTRATOR` | administrar funcionários, papéis e configurações |

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
- Ator autorizado: `STOCK_KEEPER` ou `ADMINISTRATOR`.
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
- o exemplar deve possuir status `AVAILABLE`.

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

Regra aprovada e implementada: o prazo padrão de empréstimo é de 15 dias corridos.

A `due_date` não é informada pelo cliente no momento da criação do empréstimo.

O backend calcula automaticamente:

- `loan_date`: momento do registro do empréstimo;
- `due_date`: `loan_date` + 15 dias corridos.

Exemplo:
- empréstimo realizado em 02/10/2026;
- devolução prevista em 17/10/2026.

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
- validação de que `due_date` corresponde a `loan_date + 15 dias corridos`.

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
- com o preço unitário informado para cada item;
- com `total_amount` calculado pelo backend a partir dos itens.

A venda é criada inicialmente com:

- `status = PENDING`.

O `employee_id` é obtido a partir do usuário autenticado.

#### Concorrência e integridade

- os exemplares são consultados com bloqueio transacional durante o registro;
- não é permitida a criação da venda para exemplar inexistente;
- não é permitida a criação da venda para exemplar inativo;
- não é permitida a criação da venda para exemplar que não esteja `AVAILABLE`;
- não é permitida a criação da venda para exemplar com destinação `DIDACTIC`;
- a criação da venda e de seus itens ocorre na mesma transação;
- falha na operação provoca rollback;
- conflitos de integridade resultam em erro explícito.

#### Resultado de sucesso

- HTTP 201;
- venda persistida;
- itens da venda persistidos;
- `total_amount` calculado pelo backend;
- `status = PENDING`.

#### Erros possíveis

| Situação | HTTP | Descrição |
|---|---:|---|
| Cliente não encontrado | 404 | Cliente informado não existe |
| Exemplar não encontrado | 404 | Um ou mais exemplares informados não existem ou estão inativos |
| Exemplar indisponível | 409 | Um ou mais exemplares não estão disponíveis para venda |
| Exemplar didático | 409 | Exemplar com destinação `DIDACTIC` não pode ser vendido |
| Falha de integridade | 409 | Não foi possível registrar a venda |
| Falha de banco | 500 | Não foi possível registrar a venda |

#### Testes

- registro de venda com sucesso;
- registro com múltiplos exemplares;
- cálculo automático do `total_amount`;
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

Este fluxo não implementa ainda:

- atualização do status do exemplar para `SOLD` após confirmação da venda;
- confirmação ou cancelamento da venda.

Essas regras pertencem às implementações específicas correspondentes.

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
a interface exibe a ação desabilitada e orienta o administrador a usar a
inativação. Não existe endpoint `DELETE` para usuários.

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
- Atraso significa que a data de negócio em America/Sao_Paulo ultrapassou a data de devolução nesse mesmo calendário. A data de vencimento ainda não conta como atraso.
- Cliente com usuário/perfil inativo, penalidade cadastrada ou empréstimo OPEN em atraso não pode solicitar empréstimo, solicitar compra, entrar na fila ou concluir retirada/compra. A devolução continua permitida para regularizar o exemplar.
- Compra usa o domínio existente PurchaseReservation: WAITING, NOTIFIED e FULFILLED. NOTIFIED é o estado interno de disponibilidade para retirada; não significa envio de notificação V3.
- Solicitação de compra disponível é vinculada a uma reserva NOTIFIED com exemplar comercial. A intenção da data de retirada fica em PurchaseRequest; os estados operacionais pertencem à reserva, sem um segundo ciclo de estados.
- A fila usa a ordem persistida no backend. A posição exibida conta somente WAITING anteriores da mesma obra. Destinar um exemplar atende o primeiro WAITING; novas solicitações de compra não podem passar essa fila.
- Somente exemplares comerciais ativos podem atender compras. Exemplares destinados são excluídos da disponibilidade pública e protegidos de empréstimo, inativação, conversão, troca de obra e venda a outro cliente, inclusive no banco.
- Destinação ao cliente mantém o status físico AVAILABLE; uma venda confirmada aplica SOLD e conclui a reserva de forma atômica. Uma falha mantém o exemplar e a reserva anteriores.
- A auditoria de transições registra o funcionário que executou a operação. A devolução por outro funcionário não atribui a auditoria ao responsável pela retirada original.
- Minhas reservas inclui somente WAITING/NOTIFIED; compras concluídas não aparecem. Meus empréstimos e Minhas reservas possuem mensagens explícitas para listas vazias.

Estado: `PENDING` para política de cancelamento, ausência de retirada, expiração e tratamento do primeiro cliente da fila que ficou inelegível. O backend não inventa prazos: expires_at só é apresentado quando existente.

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
- `due_date < now()`.

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
- Decisão pendente (não alterada): o enunciado "alocar para a primeira reserva elegível" conflita com a regra aprovada de que o primeiro cliente da fila, se inelegível, bloqueia a destinação. A tela segue a regra aprovada: apenas a primeira reserva da fila pode receber exemplar e o bloqueio é explicado. Pular clientes inelegíveis exige decisão de negócio e mudança no backend.
- Decisão pendente: prazo de retirada da reserva destinada, ausência, cancelamento e expiração. A tela exibe `expires_at` somente se já existir e sinaliza reserva expirada sem oferecer ação; a venda de reserva expirada é recusada pelo backend (`reservation_expired`).
- Decisão pendente: unificação do prazo de devolução entre o fluxo transacional antigo (15 dias) e a retirada V2 (um mês de calendário). A tela de balcão não exibe prazo antes da retirada e não unifica as regras.
- Limitação técnica: as consultas retornam no máximo `limit` itens (até 100), sem paginação; a tela avisa quando o limite é atingido. A posição na fila é calculada por reserva na consulta.
- Regra aprovada: a consulta de pendências do balcão é `GET /api/v1/staff/clients/{id}/pendencies`, somente leitura, com atraso pela regra V2 (calendário de America/Sao_Paulo) e sem sincronizar penalidade.
- Limitação técnica / decisão pendente: o endpoint V1 `GET /api/v1/clients/{id}/pendencies` permanece como estava (comportamento herdado, não alterado): sincroniza a penalização com regra de atraso por instante e não exige funcionário ativo. A divergência V1/V2 de atraso e de sincronização de penalidade aguarda decisão de unificação; não é classificada como defeito. O balcão não o utiliza.
- Regra aprovada (indicadores do Painel): `GET /api/v1/staff/dashboard`, somente leitura, mesmo guard de `/staff`. Definições exatas: empréstimos ativos = empréstimos `OPEN`; devoluções hoje = empréstimos com `returned_at` na data atual de America/Sao_Paulo (00:00 inclusive a 00:00 seguinte exclusive); reservas aguardando = reservas de compra `WAITING`; pendências = clientes distintos com empréstimo `OPEN` em atraso pela regra V2 (vencimento antes do início do dia de negócio atual; vencer hoje não é atraso). O cálculo de atraso é o mesmo de `has_overdue_loan`, compartilhado no repository.
- Decisão pendente (escopo atualizado em 03/10/2026): o empréstimo direto (`POST /api/v1/loans`) e a venda direta (`POST /api/v1/sales`) devem coexistir com os fluxos V2 sob a decisão do responsável de entrega incremental. Suas regras atuais não são alteradas e divergem da V2 (prazo de 15 dias corridos contra um mês de calendário; atraso por instante contra calendário de São Paulo). A unificação exige decisão de negócio. A venda direta foi implementada no balcão (Issue #126, abaixo) e o empréstimo direto também (Issue #136, abaixo).
- Regra aprovada (Acervo do balcão, Issue #124): as consultas `GET /api/v1/staff/books`, `GET /api/v1/staff/books/{id}` e `GET /api/v1/staff/copies` são somente leitura e usam o guard de `/staff` (`SELLER`/`ADMINISTRATOR`). A obra informa total e contagem por destinação apenas de exemplares ativos e não vendidos; o detalhe lista os exemplares com destinação, status e as situações `free` (livre pela definição comum) e `allocated_for_purchase`. A tela deriva o rótulo do exemplar desses fatos (Disponível, Emprestado, Reservado para venda, Venda em andamento, Vendido, Inativo).
- Regra aprovada (Acervo do balcão): categoria e inativação de obra usam `PATCH /api/v1/books/{id}`, autorizado no backend a `STOCK_KEEPER`, `MANAGER` e `ADMINISTRATOR`; `SELLER` só lê. A tela mostra as ações apenas a esses papéis (no balcão chega apenas `ADMINISTRATOR`), exige confirmação, bloqueia envio duplicado, anuncia sucesso só após 2xx e recarrega a obra após qualquer resposta. Categoria vazia é enviada como nula.
- Decisão pendente (Refs #21 e #22): editar e converter (Venda ↔ Empréstimo) exemplar e "destinação da obra" (no modelo a destinação é por exemplar, com um único valor). Não existe `PATCH /copies` nem regra de conversão ou papéis; a tela não oferece essas ações (a inclusão e a exclusão de exemplar foram entregues na Issue #135, abaixo).
- Decisão pendente: reativação de obra. O backend aceita `is_active=true` no `PATCH`, mas não há regra aprovada nem tela de referência; a interface apenas inativa e informa que a reativação não está disponível.
- Decisão pendente: exibição de preço no detalhe do acervo. A referência diz que nenhum preço foi definido na V2, mas existe `sale_price` por exemplar comercial; a tela não exibe preço.
- Limitação técnica: a busca de obras e exemplares usa também o ISBN sem hífens e o filtro de `GET /api/v1/staff/loans` passou a aceitar ISBN; o resultado é limitado por `limit` (padrão 50) e a tela avisa quando o limite é atingido.
- Regra aprovada (Empréstimos ativos e devolução no balcão, Issue #125): `/balcao/emprestimos/ativos` é uma tabela somente leitura de `GET /api/v1/staff/loans`, com atraso pela regra V2 já existente (sem regra nova); o contador "ativos • atrasados" conta os itens listados, e a tela avisa quando o limite de `limit` é atingido. `/balcao/devolucoes` localiza o empréstimo aberto por `q` (código do exemplar ou ISBN, que o backend também aceita com hífens) e registra a devolução por `POST /api/v1/staff/loans/{id}/confirm-return` com confirmação, bloqueio de envio duplicado e sucesso só após 2xx; depois de qualquer resposta a busca é refeita. Nenhuma consulta nova no backend. A frase do rodapé ("Atraso gera pendência do cliente até a devolução ser registrada") reflete a seção 20 e a seção 21 (pendência = empréstimo `OPEN` em atraso) e não cria multa nem penalidade.
- Limitação técnica: o campo de devolução usa o mesmo `q` da lista de empréstimos, que também casa nome do cliente, e-mail, título e autor; a interface rotula o campo como código do exemplar ou ISBN, mas não restringe a consulta. Um ISBN pode retornar vários empréstimos abertos da mesma obra; o funcionário escolhe o exemplar correto.
- Decisão pendente: "Fila desta obra" nas solicitações e comprovante de devolução (itens do Figma sem regra ou desenho aprovado neste recorte) seguem fora da interface. O item "Reservas" da sidebar foi entregue na Issue #127 (abaixo).
- Regra aprovada (Venda direta no balcão, Issue #126): `/balcao/vendas` busca o exemplar por código, ISBN ou título (`GET /api/v1/staff/copies`; a elegibilidade `sellable` e o motivo do bloqueio vêm do backend) e registra a venda por `POST /api/v1/sales/`, já restrito a `SELLER` e `ADMINISTRATOR` (sem ampliação de papéis), sem cliente (`client_id` opcional) e com um item. A tela pede confirmação, bloqueia envio duplicado e só mostra sucesso após 2xx. O backend cria a venda `PENDING` e o exemplar continua `AVAILABLE`: a tela diz "Venda registrada como pendente" e nunca "vendido"/"venda concluída"; depois de qualquer resposta a busca é refeita e o exemplar passa a aparecer como indisponível (venda em andamento). Exemplar didático é bloqueado no cartão e, se o POST for tentado, vale o erro de domínio existente (409, "Exemplares didáticos não podem ser vendidos."). `unit_price` enviado é o `sale_price` do exemplar retornado pelo backend, não editável; sem preço cadastrado a venda não é oferecida. Nenhuma regra, endpoint ou migration nova.
- Decisão pendente (Refs #126): confirmação e cancelamento da venda direta PENDING. Não há endpoint (a confirmação de venda V2 só atende reservas de compra), e por isso o estado final da referência ("Venda registrada", estoque antes/depois, status "Vendido") não pode ser exibido; também não há comprovante.
- Decisão pendente (Refs #126): validação do preço no backend. `POST /api/v1/sales/` aceita qualquer `unit_price >= 0` enviado pelo cliente, sem compará-lo ao `sale_price` do exemplar; a tela envia o preço do exemplar, mas a garantia não é do backend. Também pendente: venda para cliente identificado (o endpoint aceita `client_id`, a referência não o mostra) e a possibilidade de duas vendas pendentes do mesmo exemplar, hoje barrada na busca por `free`, mas não pelo endpoint (que só exige `AVAILABLE`).
- Regra aprovada (rotas do balcão, Issue #126): as reservas de compra foram movidas de `/balcao/vendas` para `/balcao/reservas` sem alteração funcional, para liberar `/balcao/vendas` à venda direta. O item de menu "Reservas" e o redesenho foram entregues na Issue #127 (abaixo); o atalho "Reservas" em Clientes continua levando a `/balcao/reservas`.
- Regra aprovada (Reservas de compra no balcão, Issue #127): item "Reservas" na sidebar (após "Vendas") e rotas `/balcao/reservas` (fila por obra) e `/balcao/reservas/:id?cliente=` (atender, confirmar e venda concluída), sem endpoint, regra ou migration novos. A lista usa `GET /api/v1/staff/purchase-reservations` (busca por título, nome, e-mail ou código do exemplar; filtro de cliente vindo de "Clientes") e agrupa por obra no frontend; a posição exibida é a `queue_position` do backend (só reservas aguardando). A destinação usa `POST /api/v1/staff/books/{id}/allocate-purchase` com diálogo de confirmação (apenas a primeira da fila elegível; o bloqueio é explicado e a fila não é saltada).
- Regra aprovada (Atender reserva): a tela localiza a reserva na mesma consulta (filtrada pelo cliente da URL; não há consulta por id), mostra cliente, situação de elegibilidade, exemplar destinado e `expires_at` somente se persistido, e exige que o código digitado seja igual (após remover espaços nas pontas) ao `allocated_copy_barcode` devolvido pelo backend antes de avançar. A etapa de resumo confirma a venda por `POST /api/v1/staff/purchase-reservations/{id}/confirm-sale`, bloqueia envio duplicado e só mostra "Venda da reserva concluída" após 2xx. O texto "exemplar ficará Vendido e a reserva será concluída" reflete o gatilho de banco já existente (venda confirmada → exemplar `SOLD`, reserva `FULFILLED`, coberto em `test_staff_desk_postgres`). Erros de domínio (`reservation_expired`, `reservation_not_ready`, `client_ineligible` etc.) são exibidos com a mensagem do backend, sem sucesso, e a reserva é recarregada.
- Regra aprovada (estados de recuperação): "Nenhuma reserva encontrada" aparece quando uma busca ou o filtro de cliente não retorna reservas (com "Limpar busca"); sem filtro, a tela diz que não há reservas em andamento. "Reserva fora do prazo" aparece somente quando o backend informa `expired` (`expires_at` persistido já vencido); a tela não calcula nem inventa prazo, não oferece venda e leva a "Consultar fila".
- Decisão pendente (Refs #127): política de prazo de retirada (duração, criação de `expires_at`, cancelamento e transição para `EXPIRED`); hoje nenhum fluxo define `expires_at`, então a referência com "Prazo de retirada: 06/10/2026" só se aplica se o dado existir. Também pendente: o rótulo "Status: consultar situação atualizada da reserva" e "Origem: reserva de compra · prioridade ativa" das referências não têm dado equivalente e não são exibidos além do que o backend informa.
- Divergências da referência (Issue #127): o bloco "Estoque comercial disponível: 1 → 0" não é exibido (o backend não devolve estoque antes/depois); "Fulano passa à 1ª posição" só aparece se uma nova consulta pós-venda retornar a próxima reserva aguardando da obra; a ordinal "1ª" da reserva com exemplar destinado não é exibida porque `queue_position` só existe para reservas aguardando; "Consultar outra obra" apenas foca o campo de busca; "Registrar outra venda" leva à venda direta (`/balcao/vendas`); a conferência do exemplar é por digitação do código (sem seletor de exemplares).
- Limitação técnica (Issue #127): a reserva em "Atender" é achada na lista limitada a 50 itens; sem filtro de cliente na URL e com mais de 50 reservas ativas ela pode não aparecer (a tela informa que ela não está mais em andamento). Sem endpoint de detalhe por id.
- Regra aprovada (Controle de pendências no balcão, Issue #128): `/balcao/clientes` ("Controle de pendências") busca clientes por nome ou e-mail (`GET /api/v1/staff/clients`, mínimo de 2 caracteres) e consulta `GET /api/v1/staff/clients/{id}/pendencies`, somente leitura, com atraso pela regra V2 e sem sincronizar penalidade. Resultado único é consultado automaticamente; vários resultados são listados para escolha. O cartão mostra "Pendência ativa" com obra, exemplar, vencimento e dias de atraso de cada empréstimo em atraso, ou "Sem pendência"; avisos de penalizado e cadastro inativo vêm de `is_penalized`/`is_active`. A frase "Pendência = empréstimo não devolvido após a data prevista" reflete a seção 20 (empréstimo `OPEN` em atraso). Os atalhos Solicitações, Empréstimos ativos e Reservas guardam o cliente como filtro das respectivas telas. Nenhum endpoint, regra ou migration novos.
- Limitação técnica (Issue #128): busca por CPF. O modelo de cliente não possui CPF, portanto a referência "Nome, CPF ou e-mail" é atendida apenas por nome ou e-mail e a tela não menciona CPF.
- Divergências da referência (Issue #128): o cartão exibe também e-mail, avisos de penalização/inativo e os atalhos; "Exemplar #00127" mostra o código real do exemplar; a lista de escolha para múltiplos resultados e o estado "Sem pendência" não existem no desenho. A frase "Enquanto ativa, novas operações que exigem cliente apto devem ser bloqueadas" segue a seção 20 (operações de circulação reavaliam pendências), mas o bloqueio é do backend, não desta tela.
- Decisão pendente (Refs #128): divergência entre o `GET /api/v1/clients/{id}/pendencies` V1 (sincroniza penalização, atraso por instante) e o V2 do balcão (somente leitura, calendário de America/Sao_Paulo); o V1 não foi alterado e não é usado pelo balcão. Também pendente: listar mais de 100 empréstimos em atraso de um cliente (limite interno da consulta) e gestão manual de penalidade na interface.
- Regra aprovada (Inclusão de exemplar no balcão, Issue #135): `/balcao/acervo/:id/exemplares/novo` usa o endpoint existente `POST /api/v1/copies/` (`STOCK_KEEPER` e `ADMINISTRATOR`; no balcão chega apenas `ADMINISTRATOR`, pois `STOCK_KEEPER` não acessa `/balcao`; `SELLER` não vê o botão "Novo exemplar" e a tela recusa o formulário). Campos enviados: obra, código (obrigatório, até 100 caracteres), finalidade (Empréstimo = `DIDACTIC`, Venda = `COMMERCIAL`) e preço de venda, obrigatório para Venda e proibido para Empréstimo (validação do backend replicada na tela). O status inicial é definido pelo backend (`AVAILABLE`). Obra inativa não aceita exemplar (404 do backend; a tela não oferece o formulário). Sucesso só após 2xx; a nova quantidade vem da recarga da obra. Envio duplicado é bloqueado.
- Regra aprovada (código duplicado): o backend responde 409 em violação de unicidade do código; a tela mantém os dados, marca o código como já cadastrado, informa que nenhum exemplar foi incluído e libera o envio ao trocar o código.
- Limitação técnica (Issue #135): `POST /api/v1/copies/` devolve o 409 como `HTTPException` com mensagem e sem o código estável `duplicate_barcode` (existente apenas no cadastro de obra). A tela reconhece o 409 do endpoint como código duplicado; qualquer outra violação de integridade também retornaria 409 com a mesma mensagem.
- Divergências da referência (Issue #135, inclusão): o formulário tem o campo "Preço de venda" quando a finalidade é Venda, exigido pelo backend e ausente do desenho; condição e data de aquisição, aceitas pelo backend, não aparecem no desenho e não são enviadas; a quantidade "de 4 para 5" usa o total real da obra antes e depois; "Ver exemplares" volta aos detalhes da obra.
- Regra aprovada (Inativação de obra, Issue #135): usa `PATCH /api/v1/books/{id}` com `is_active=false`. O modal "Inativar <obra>?" mostra a "Situação verificada" lida dos exemplares carregados (quantidade vinculada, exemplares emprestados ou reservados para venda) e exige "Confirmar inativação" (o backend bloqueia a inativação enquanto houver operação em andamento, regra abaixo); após 2xx a tela exibe "<obra> foi inativada. O histórico foi preservado." e o cartão "Situação da obra" (inativa, exemplares vinculados, indisponível) com "Voltar ao acervo".
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03 (Issue #135, inativação de obra bloqueada): `PATCH /api/v1/books/{id}` com `is_active=false` é bloqueado enquanto houver operação em andamento: empréstimo `OPEN` de qualquer exemplar da obra, solicitação de retirada pendente (`loan_id IS NULL`) da obra ou reserva de compra `WAITING` ou `NOTIFIED` (aguardando ou com exemplar destinado) da obra. A validação fica no service, que trava o livro e os exemplares da obra (`FOR UPDATE`, o mesmo padrão dos fluxos de circulação) antes de contar, e só vale quando `is_active` passa de verdadeiro para falso; as demais alterações da obra não são afetadas. O bloqueio responde 409 `book_has_active_operations` com `details.counts` (`open_loans`, `pending_loan_requests`, `purchase_reservations`) e `details.links` (até 10 por tipo: `type`, `copy_barcode` e `client_name`; o nome do cliente só é devolvido a quem tem `ADMINISTRATOR` ou `SELLER`, e os demais papéis recebem apenas tipo, código do exemplar e contagens), e nada é alterado (rollback). Exemplares e empréstimos permanecem intactos. Reativação continua fora do escopo (decisão pendente acima). Antes desta regra, nenhum serviço, trigger ou constraint bloqueava a inativação (a única trava, `trg_active_book_has_copy`, exige exemplar ativo só para obra ativa).
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03 (Issue #135, exclusão de exemplar): `DELETE /api/v1/copies/{id}`, restrito a `STOCK_KEEPER` e `ADMINISTRATOR` com cadastro de funcionário ativo (no balcão chega apenas `ADMINISTRATOR`; `SELLER` recebe 403, sem token 401, usuário ou funcionário inativo 403). A exclusão é física e só é permitida se o exemplar estiver `AVAILABLE` e sem histórico: nenhum empréstimo (aberto ou encerrado), nenhum item de venda, nenhuma reserva de compra que o referencie (`allocated_copy_id` ou `fulfilled_copy_id`) e nenhuma solicitação vinculada (de retirada, via empréstimo; de compra, via reserva). Também é bloqueada se for o último exemplar ativo de uma obra ativa. Bloqueio: 409 com `code` do primeiro motivo encontrado, na ordem `copy_not_available`, `copy_has_history`, `last_active_copy`, `details.reasons[]` (todos os motivos, com `code` e `message`) e `details.history` (`loans`, `sales`, `purchase_reservations`, `requests`). Exemplar inexistente: 404 `copy_not_found`; funcionário sem cadastro ativo: 403 `employee_record_required`; sucesso: 200 `{id, book_id, barcode, deleted}`. A operação é atômica: o service trava o livro e depois o exemplar (`FOR UPDATE`), reavalia as condições e exclui na mesma transação, serializando com empréstimo, venda e destinação concorrentes; se o exemplar sumir durante a espera, 404. Se a FK `RESTRICT` do banco ou o gatilho adiado `trg_copy_keeps_active_book_valid` barrar algo não previsto, o resultado é bloqueio (`copy_has_history` ou `last_active_copy`), nunca 500; falha de persistência desconhecida é 500 `copy_delete_persistence_error` com rollback. Auditoria: o `trg_audit_copies` registra o `DELETE` com o funcionário responsável (`set_config('libstock.employee_id')`) e o valor antigo do exemplar. Nenhuma migration foi necessária.
- Regra aprovada — decisão delegada pelo responsável em 2026-10-03 (Issue #135, obra inativa em empréstimo e venda diretos): `POST /api/v1/loans/` e `POST /api/v1/sales/` travam o livro do exemplar antes do exemplar (ordem livro → exemplar, a mesma da inativação e dos fluxos V2; na venda, vários livros em ordem de id) e recusam obra inativa com 409 `book_inactive`, sem gravar. Assim, uma inativação em andamento serializa com esses registros: quem pega o lock primeiro define o resultado. A validação de destinação continua como estava: a venda já bloqueia exemplar didático; para o empréstimo não há regra aprovada de exigir exemplar didático (ver Issue #136), então nada foi inventado.
- Divergências da referência (Issue #135, exclusão e bloqueio): os estados "Exclusão bloqueada", "Inativação bloqueada" e "Exemplar excluído" aparecem na própria página de detalhes da obra (cartão de bloqueio e mensagem de sucesso), não em telas separadas; o bloqueio de exemplar lista os motivos e contagens de histórico devolvidos pelo backend, sem cliente e data de devolução (o 409 não os retorna); "Consultar empréstimo" não existe, o bloqueio de exemplar tem "Voltar aos exemplares" e o de obra tem "Consultar empréstimos" (`/balcao/emprestimos/ativos`) e "Consultar reservas" (`/balcao/reservas`); o botão "Excluir exemplar" aparece em cada linha (só para papéis autorizados) e é antecipado como desabilitado, com o motivo, quando o status já indica bloqueio (não disponível, reservado para venda ou último exemplar ativo), mas a decisão final é do backend; o painel lateral "Editando exemplar" do desenho não existe (edição de exemplar segue sem regra aprovada); "Quantidade da obra após exclusão: 5 → 4" usa o total real carregado.
- Regra aprovada (Empréstimo direto no balcão, Issue #136; proposta condicional EAP 1.2.9–1.2.13, incluída por decisão do responsável de entrega incremental): `/balcao/emprestimos/novo` (acessível pelo card "Novo empréstimo" de Empréstimos/Início e pelo card "Empréstimo" do Painel) escolhe o cliente por `GET /api/v1/staff/clients` (nome ou e-mail, mínimo de 2 caracteres) e o exemplar por `GET /api/v1/staff/copies` (código, ISBN ou título), revisa e registra por `POST /api/v1/loans/`, endpoint existente restrito a `SELLER` e `ADMINISTRATOR` (sem ampliação de papéis; `SELLER` pode registrar). O corpo contém apenas `client_id` e `copy_id`. A tela pede confirmação explícita, bloqueia envio duplicado e só mostra "Empréstimo registrado" após 2xx. Nenhum endpoint, regra, consulta ou migration novos.
- Regra aprovada (prazo no empréstimo direto): o prazo é calculado pelo backend (regra V1 de 15 dias corridos, seção Empréstimo). A tela não calcula nem afirma prazo antes do registro ("calculada automaticamente ao registrar", sem citar a duração) e, depois de 2xx, exibe `loan_date` e `due_date` retornados, no calendário de America/Sao_Paulo.
- Regra aprovada (elegibilidade antecipada, sem regra nova): o cliente selecionado com `eligible=false` (conta inativa, penalizado ou empréstimo em atraso pela regra V2) bloqueia a revisão e mostra os motivos; o exemplar só é oferecido quando é didático, livre (mesma definição de exemplar livre da retirada V2, que exclui destinados e com venda em andamento) e de obra ativa, o mesmo critério dos exemplares elegíveis da retirada. Exemplares comerciais, emprestados, reservados, vendidos, inativos ou de obra inativa aparecem desabilitados com o motivo. É uma antecipação de leitura: a decisão final é do backend.
- Regra aprovada (empréstimo bloqueado): o estado "Empréstimo bloqueado" vem dos erros de domínio reais de `POST /api/v1/loans/` e usa a mensagem do backend: `client_not_found` (404), `client_inactive` (403) e `client_has_pending` (409) levam ao bloqueio de cliente ("Consultar pendências", "Selecionar outro cliente"); 404 (exemplar não encontrado ou inativo) e 409 (exemplar indisponível ou conflito de integridade) levam ao bloqueio de exemplar ("Atualizar seleção", que refaz a busca). Falhas inesperadas (por exemplo 500 ou rede) mantêm a revisão com a mensagem e sem sucesso, orientando a conferir os empréstimos ativos antes de repetir. Nenhum sucesso é exibido sem 2xx.
- Divergências da referência (Issue #136): sem "Baixar comprovante" e sem a frase "O comprovante estará disponível" (não há endpoint nem regra de comprovante; fora do escopo); o campo "Buscar por nome, CPF ou e-mail" aceita apenas nome ou e-mail (o modelo de cliente não tem CPF, Issue #128); "Retirada: hoje" usa a data de negócio de America/Sao_Paulo e, no registro, a `loan_date` do backend; "Devolução prevista" vem de `due_date` do backend; "Status do exemplar: Emprestado" só é exibido se a resposta traz o empréstimo `OPEN`, que o gatilho `trg_apply_loan_copy_state` converte em exemplar `BORROWED`; busca de cliente e de exemplar por botão em vez de lista suspensa; "Novo empréstimo" no final volta ao formulário vazio e há o link "Ver empréstimos ativos". Notas para desenvolvedores das referências não são interface.
- Decisão pendente (Refs #136, prazo): o empréstimo direto usa o prazo V1 (`loan_date` + 15 dias corridos, instante UTC) e a retirada V2 de solicitação usa um mês de calendário contado da retirada (seção 19). Não foram unificados; unificar exige decisão de negócio e mudança no backend. Também diferem o cálculo de atraso (instante no V1, calendário de America/Sao_Paulo no V2): um cliente cujo vencimento ainda é hoje pode aparecer como apto (`eligible=true`, regra V2) e ainda assim ser bloqueado pelo `POST /api/v1/loans/` com `client_has_pending`; a tela mostra o bloqueio real do backend.
- Lacuna do backend (Issue #136): `POST /api/v1/loans/` não verifica a destinação do exemplar (aceita exemplar comercial `AVAILABLE`; a conferência de obra ativa passou a existir na Issue #135, `book_inactive`); a restrição a exemplar didático livre vem apenas da tela. Os 409 de exemplar indisponível e de conflito de integridade não têm código estável (`HTTPException`), e a tela os distingue pelo status HTTP. O gatilho `trg_link_client_loan_request` vincula ao novo empréstimo a solicitação de empréstimo pendente do mesmo cliente e da mesma obra, se existir; não há tela nem regra aprovada sobre esse efeito colateral (decisão pendente).- Fora do escopo: comprovante digital, cancelamento de reservas, notificações e gestão manual de penalidade pela interface.
- Regra aprovada (Feedback por snackbar e estados de recuperação, Issue #137): componente compartilhado `app-snackbar` com as quatro variantes da referência (sucesso, erro, atenção, informação), hospedado uma única vez no layout do balcão e descartado ao sair dele. Erros usam região `role="alert"` (assertiva); as demais, `role="status"` (educada); as duas regiões existem desde o início para o anúncio funcionar, o foco nunca é movido, há botão "Fechar" e Esc fecha quando o foco está na mensagem. Sucesso e informação sem ação somem após 8 s; erro, atenção e mensagens com ação ficam até o fechamento (a referência não indica tempo; os 8 s são decisão de implementação). Orientação da referência aplicada: sucesso e erro de uma ação vão para o snackbar; bloqueios e decisões (cartões de bloqueio, "Operação bloqueada", tela de venda/empréstimo concluído, fora do prazo) continuam como estado, sem repetir a mesma mensagem no snackbar; confirmação destrutiva continua em diálogo modal.
- Regra aprovada (feedback nas operações de escrita do balcão, Issue #137): sucesso só após 2xx, com os textos já existentes por operação (retirada, devolução, destinação, categoria, inativação, exclusão de exemplar). Recusa de domínio 4xx usa a mensagem do backend: 409 como atenção e as demais como erro. Falha de rede (status 0) ou 5xx mostra o estado "Não foi possível salvar" (referência 07_2: "A operação não foi concluída… Atualize a consulta antes de repetir a operação para evitar registros duplicados") com "Atualizar consulta" e "Voltar", sem snackbar. A tela nunca reenvia sozinha; como o resultado pode ser incerto, a nova tentativa é manual, depois de atualizar a consulta (a lista é recarregada após qualquer resposta) e novo diálogo de confirmação. Não há idempotência no backend, por isso não existe botão "Tentar novamente" que reenvie a escrita.
- Divergências da referência (Issue #137): os textos prontos da referência ("Devolução registrada com sucesso.", "Venda registrada com sucesso." etc.) não são usados porque as mensagens atuais descrevem o comportamento real (por exemplo, a venda direta fica pendente e o exemplar não é "vendido"); a variante informação existe no componente, mas nenhuma tela do balcão a usa ainda (a posição na fila é exibida em cartões); a tela de atendimento de reserva, a de inclusão de exemplar e o empréstimo direto mostram o sucesso em estado próprio (referências 02, 03 e 06) e por isso não disparam snackbar; as falhas de carregamento (consultas GET) seguem em alerta com "Tentar novamente", que é seguro por ser leitura.

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
- O empréstimo direto (`LoanService`) mantém o prazo existente de 15 dias corridos. A confirmação da solicitação V2 (`CirculationService`) mantém um mês de calendário. A divergência exige uma decisão explícita e unificação futura; não foi alterada silenciosamente na resolução de conflitos.
- O serviço de pendências recebido da main usa vencimento por instante (`due_date < now()`); o acompanhamento V2 usa o calendário de America/Sao_Paulo. A sincronização das políticas e da penalização entre os serviços permanece pendente.
- A home mantém a disponibilidade por modalidade e os links para detalhes da V2. O contrato administrativo de consulta de disponibilidade e o cadastro de exemplares foram preservados.
