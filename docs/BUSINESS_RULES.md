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
- persistência de entidades de circulação.

### Planejado, mas não disponível

- empréstimos;
- devoluções;
- reservas;
- vendas;
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

### Empréstimo

Status: `PENDING`.

### Devolução

Status: `PENDING`.

### Venda

Status: `PENDING`.

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
- penalidades de clientes;
- política de reservas;
- confirmação e cancelamento de vendas;
- criação de funcionário e usuário na mesma transação;
- papéis oficiais da aplicação;
- pertencimento de cada fluxo à V1, V2 ou V3.

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
