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

Status: `PENDING`.

Pré-condições previstas:
- cliente existente;
- cliente ativo;
- cliente sem pendências de empréstimos;
- exemplar disponível e compatível com a operação.

A validação da situação do cliente é realizada pelo fluxo
`GET /api/v1/clients/{client_id}/validation`.

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

A exclusão física de usuários não pertence ao contrato implementado. Até serem definidos os impactos sobre histórico, auditoria e referências de circulação, a interface exibe a ação desabilitada e orienta o administrador a usar a inativação. Não existe endpoint `DELETE` para usuários.

## 17. Controle de pendências e penalização de clientes

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

Os serviços de consulta e sincronização de penalização estão preparados para essa integração. Os fluxos transacionais de empréstimo, devolução e reserva ainda dependem da implementação de seus respectivos services e endpoints.
