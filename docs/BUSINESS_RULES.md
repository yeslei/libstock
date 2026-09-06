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
| `STOCK_KEEPER` | cadastrar obras e operar acervo, se autorizado |
| `MANAGER` | administrar destaques e funções gerenciais |
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

Regra aprovada: toda obra nova deve ser persistida com um primeiro exemplar
ativo na mesma transação. A obra, o exemplar e seus registros de auditoria só
podem ser confirmados em conjunto; qualquer falha provoca rollback integral.
O status do exemplar inicial não integra o payload: o backend sempre o persiste
como `AVAILABLE` e força `is_active=true`.

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
