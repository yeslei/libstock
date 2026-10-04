# Escopo UX da V1 do LibStock — revisado por papéis e regras de negócio

## 1. Objetivo da V1

A V1 do LibStock deve entregar o núcleo funcional de autenticação, consulta e gestão de acervos, respeitando a separação entre obra bibliográfica e exemplar físico.

A versão deve permitir:

* criar conta e autenticar usuários;
* consultar e atualizar o próprio perfil;
* explorar o catálogo;
* pesquisar por título, autor, ISBN e código de barras;
* consultar obras, exemplares e disponibilidade;
* cadastrar, editar e inativar obras;
* cadastrar, editar e inativar exemplares;
* definir a destinação inicial dos exemplares;
* controlar permissões por papel;
* cadastrar, consultar, atualizar e inativar clientes;
* cadastrar, consultar, atualizar e inativar funcionários;
* consultar pendências de clientes;
* preparar as modalidades de venda, empréstimo e troca sem executar as transações da V2.

Não fazem parte da V1:

* registro de vendas;
* registro de empréstimos;
* registro de devoluções;
* reservas;
* descoberta e conclusão de trocas;
* chat;
* notificações;
* auditoria visual;
* relatórios de circulação.

## 2. Papéis oficiais

A V1 deve utilizar exclusivamente os papéis consolidados no banco:

| Papel           | Persona correspondente   | Responsabilidade                                                           |
| --------------- | ------------------------ | -------------------------------------------------------------------------- |
| `USER`          | Cliente/Leitor           | Consultar o acervo e gerenciar o próprio perfil                            |
| `SELLER`        | Atendente/Vendedor       | Consultar clientes, pendências e disponibilidade                           |
| `STOCK_KEEPER`  | Estoquista/Bibliotecário | Gerenciar obras, exemplares e estoque                                      |
| `ADMINISTRATOR` | Gerente/Dono             | Administrar acervo, usuários, funcionários, permissões e decisões críticas |

Os nomes `ATTENDANT` e `MANAGER` são legados e não devem aparecer na interface, nas novas histórias ou nos novos componentes.

## 3. Princípios de autorização

As permissões devem ser verificadas em três níveis:

1. proteção da rota no frontend;
2. visibilidade ou habilitação da ação;
3. autorização efetiva no backend.

Ocultar um botão não substitui a autorização no servidor.

O `ADMINISTRATOR` herda todas as capacidades internas da V1.

Quando o banco permitir vários papéis por usuário, a interface deve:

* usar o termo “Papéis e permissões”;
* exibir todos os papéis atribuídos;
* calcular as capacidades pela união dos papéis;
* impedir combinações inválidas;
* impedir a remoção do último administrador ativo.

Se o produto decidir limitar cada funcionário a um único papel funcional, essa regra deverá ser formalizada e garantida por constraint ou validação transacional.

## 4. Permissões por papel

### 4.1 Visitante anônimo

Pode:

* acessar o catálogo;
* pesquisar obras;
* navegar por gênero;
* consultar detalhes públicos da obra;
* consultar disponibilidade agregada;
* criar conta;
* entrar no sistema.

Não pode:

* acessar dados privados de clientes ou funcionários;
* administrar obras ou exemplares;
* consultar códigos de barras completos de todos os exemplares;
* executar operações de circulação;
* acessar painéis administrativos.

### 4.2 `USER` — Cliente/Leitor

Pode:

* acessar o catálogo;
* pesquisar e filtrar obras;
* consultar detalhes e disponibilidade;
* acessar o painel pessoal;
* consultar e atualizar os próprios dados;
* encerrar as próprias sessões;
* sair do sistema.

Não pode:

* administrar o catálogo institucional;
* cadastrar ou editar exemplares;
* acessar outros clientes;
* acessar funcionários;
* alterar papéis;
* converter destinação;
* iniciar vendas, empréstimos, reservas ou trocas na V1.

Históricos de empréstimos, compras, reservas, trocas e notificações não devem ser apresentados na V1 enquanto os respectivos módulos não estiverem implementados.

### 4.3 `SELLER` — Atendente/Vendedor

Pode:

* acessar o catálogo;
* pesquisar por título, autor, ISBN e código de barras;
* consultar a disponibilidade dos exemplares;
* acessar o painel operacional da V1;
* cadastrar clientes, quando o endpoint correspondente estiver disponível;
* consultar clientes;
* atualizar dados permitidos de clientes;
* consultar pendências;
* inativar clientes, quando autorizado pela regra de negócio.

Não pode:

* cadastrar ou editar obras;
* gerenciar exemplares;
* alterar destinação;
* cadastrar funcionários;
* alterar papéis;
* executar venda, empréstimo ou devolução na V1;
* acessar auditoria.

Enquanto os endpoints transacionais da V2 não existirem, o painel do vendedor deve apresentar somente consulta e gestão de clientes, sem botões funcionais de venda ou empréstimo.

### 4.4 `STOCK_KEEPER` — Estoquista/Bibliotecário

Pode:

* acessar o painel de estoque;
* consultar o catálogo;
* cadastrar obra e exemplar inicial;
* editar dados bibliográficos;
* cadastrar novos exemplares;
* editar condição e dados operacionais permitidos;
* definir a destinação inicial do exemplar;
* consultar quantidades e disponibilidade;
* inativar obra ou exemplar quando não houver impedimento de integridade.

Não pode:

* gerenciar clientes;
* cadastrar funcionários;
* alterar papéis;
* consultar auditoria;
* executar operações transacionais da V2;
* converter exemplar didático em comercial quando a trigger `guard_copy_integrity` exigir administrador.

A definição inicial da destinação é diferente da conversão posterior:

* no cadastro: `STOCK_KEEPER` e `ADMINISTRATOR`;
* na conversão de exemplar existente: somente `ADMINISTRATOR`, enquanto essa for a regra vigente no banco.

### 4.5 `ADMINISTRATOR` — Gerente/Dono

Pode:

* acessar todos os módulos internos da V1;
* administrar obras e exemplares;
* definir e converter destinações;
* cadastrar, consultar, atualizar e inativar clientes;
* cadastrar, consultar, atualizar e inativar funcionários;
* atribuir e remover papéis;
* consultar pendências;
* realizar ações críticas autorizadas;
* administrar o contexto da conta ou instituição, quando esse vínculo estiver implementado.

Não pode, na V1:

* acessar uma tela de auditoria ainda pertencente à V3;
* executar funcionalidades da V2 que não possuam backend;
* remover o próprio acesso se isso deixar o sistema sem administrador;
* remover o último `ADMINISTRATOR` ativo.

## 5. Matriz de acesso

| Funcionalidade              | Visitante | `USER` |   `SELLER`  | `STOCK_KEEPER` | `ADMINISTRATOR` |
| --------------------------- | :-------: | :----: | :---------: | :------------: | :-------------: |
| Explorar catálogo           |    Sim    |   Sim  |     Sim     |       Sim      |       Sim       |
| Pesquisar obras             |    Sim    |   Sim  |     Sim     |       Sim      |       Sim       |
| Consultar detalhes públicos |    Sim    |   Sim  |     Sim     |       Sim      |       Sim       |
| Gerenciar próprio perfil    |    Não    |   Sim  |     Sim     |       Sim      |       Sim       |
| Consultar clientes          |    Não    |   Não  |     Sim     |       Não      |       Sim       |
| Cadastrar/editar clientes   |    Não    |   Não  | Condicional |       Não      |       Sim       |
| Consultar pendências        |    Não    |   Não  |     Sim     |       Não      |       Sim       |
| Alterar penalidade          |    Não    |   Não  | Condicional |       Não      |       Sim       |
| Cadastrar obras             |    Não    |   Não  |     Não     |       Sim      |       Sim       |
| Editar obras                |    Não    |   Não  |     Não     |       Sim      |       Sim       |
| Inativar obras              |    Não    |   Não  |     Não     |   Condicional  |       Sim       |
| Cadastrar exemplares        |    Não    |   Não  |     Não     |       Sim      |       Sim       |
| Editar exemplares           |    Não    |   Não  |     Não     |       Sim      |       Sim       |
| Definir destinação inicial  |    Não    |   Não  |     Não     |       Sim      |       Sim       |
| Converter destinação        |    Não    |   Não  |     Não     |       Não      |       Sim       |
| Gerenciar funcionários      |    Não    |   Não  |     Não     |       Não      |       Sim       |
| Atribuir papéis             |    Não    |   Não  |     Não     |       Não      |       Sim       |
| Consultar auditoria         |    Não    |   Não  |     Não     |       Não      |        V3       |

“Condicional” significa que a ação somente pode ser apresentada como funcional depois que sua regra e seu endpoint estiverem confirmados.

## 6. Modelo do domínio apresentado na interface

### 6.1 Obra bibliográfica

Uma obra representa os dados bibliográficos compartilhados:

* título;
* autor;
* ISBN;
* gênero;
* editora;
* edição;
* ano;
* capa;
* situação ativa ou inativa.

### 6.2 Exemplar físico

Um exemplar representa uma unidade física:

* código de barras;
* condição;
* destinação;
* estado;
* disponibilidade;
* preço, quando comercial;
* situação ativa ou inativa.

Uma obra pode possuir diversos exemplares, cada um com destinação, condição e estado diferentes.

A interface não deve atribuir à obra um único estado ou uma única destinação. A listagem administrativa de obras deve mostrar valores agregados, como:

* total de exemplares;
* quantidade de didáticos;
* quantidade de comerciais;
* quantidade de disponíveis.

A situação individual deve aparecer na gestão dos exemplares.

## 7. Regras de cadastro do acervo

### 7.1 Cadastro de obra

O cadastro de uma obra ativa deve incluir seu primeiro exemplar ativo na mesma operação transacional.

Campos obrigatórios da obra:

* título;
* autor;
* demais campos exigidos pelo contrato vigente.

Campos obrigatórios do primeiro exemplar:

* código de barras;
* destinação;
* condição;
* estado inicial;
* preço, quando comercial.

O frontend não deve apresentar sucesso antes da confirmação da persistência da obra e do exemplar.

### 7.2 Destinação

Todo exemplar deve possuir uma destinação válida.

A interface deve distinguir:

* definição inicial da destinação;
* conversão posterior da destinação.

Exemplar comercial:

* exige preço válido;
* pode ser sinalizado como disponível para venda;
* não deve ser vendido na V1.

Exemplar didático:

* não deve possuir preço de venda;
* deve ter venda bloqueada;
* pode ser sinalizado como disponível para empréstimo;
* não deve ser emprestado na V1.

### 7.3 Disponibilidade

A disponibilidade deve ser calculada a partir dos exemplares e de seus estados.

Não deve existir disponibilidade operacional única atribuída diretamente à obra.

Na V1, a interface pode informar:

* disponível para consulta;
* possui exemplar didático disponível;
* possui exemplar comercial disponível;
* temporariamente indisponível;
* sem exemplar ativo.

Esses estados não devem se transformar em botões transacionais antes da V2.

## 8. Gestão de clientes

A gestão de clientes deve contemplar:

* listagem;
* busca por nome ou e-mail;
* cadastro assistido, quando permitido;
* consulta;
* atualização;
* inativação;
* situação cadastral;
* indicador de pendência.

Permissões:

* `SELLER`: consulta e operações explicitamente autorizadas;
* `ADMINISTRATOR`: administração completa;
* demais papéis: sem acesso.

Aplicação ou remoção de penalidades deve permanecer restrita até que sejam definidos:

* papéis autorizados;
* justificativa obrigatória;
* histórico;
* impacto sobre operações futuras.

## 9. Gestão de funcionários e papéis

Somente `ADMINISTRATOR` pode acessar a gestão de funcionários.

O módulo deve permitir:

* cadastrar funcionário;
* consultar funcionário;
* atualizar dados;
* inativar acesso;
* atribuir papéis oficiais;
* remover papéis autorizados;
* visualizar situação da conta.

A interface deve impedir:

* atribuição de papel inexistente;
* falso sucesso sem persistência;
* remoção do último administrador;
* remoção acidental do próprio acesso;
* alteração de papel sem confirmação;
* duplicidade de e-mail ou código funcional.

## 10. Inventário de telas da V1

| ID  | Tela                          | Rota                                              | Acesso                          |
| --- | ----------------------------- | ------------------------------------------------- | ------------------------------- |
| T01 | Login                         | `/login`                                          | Visitante                       |
| T02 | Cadastro de conta             | `/register`                                       | Visitante                       |
| T03 | Catálogo público              | `/`                                               | Todos                           |
| T04 | Obras por gênero              | `/generos/:slug`                                  | Todos                           |
| T05 | Detalhes da obra e exemplares | `/obras/:id`                                      | Todos, com ações condicionadas  |
| T06 | Painel por papel              | `/painel`                                         | Autenticados                    |
| T07 | Perfil e sessões              | `/perfil`                                         | Autenticados                    |
| T08 | Gestão de obras               | `/gestao/obras`                                   | `STOCK_KEEPER`, `ADMINISTRATOR` |
| T09 | Cadastro/edição de obra       | `/gestao/obras/nova` e `/gestao/obras/:id/editar` | `STOCK_KEEPER`, `ADMINISTRATOR` |
| T10 | Gestão de exemplares          | `/gestao/obras/:id/exemplares`                    | `STOCK_KEEPER`, `ADMINISTRATOR` |
| T11 | Gestão de clientes            | `/gestao/clientes`                                | `SELLER`, `ADMINISTRATOR`       |
| T12 | Gestão de usuários            | `/gestao/usuarios`                                | `ADMINISTRATOR`                 |
| T13 | Cadastro de usuário           | `/gestao/funcionarios`                            | `ADMINISTRATOR`                 |
| T14 | Edição de usuário             | `/gestao/usuarios/:id/editar`                     | `ADMINISTRATOR`                 |

Criação e edição reutilizam o mesmo template. Drawers, modais, confirmações e estados de erro não são contabilizados como telas independentes.

Na gestão de usuários, o botão “Cadastrar novo usuário” conduz à tela de
cadastro já existente em `/gestao/funcionarios`. Não existe a rota
`/gestao/usuarios/novo`. A exclusão definitiva permanece pendente e, seguindo a
referência da Issue #131, não é mais exibida na listagem; a inativação é a ação
operacional disponível e fica na tela de edição, com confirmação.

## 11. Navegação por papel

### Visitante

* Início;
* Explorar;
* Categorias;
* Entrar;
* Criar conta.

### `USER`

* Painel;
* Explorar;
* Perfil;
* Sair.

### `SELLER`

* Painel;
* Explorar;
* Balcão (V2, `/balcao`);
* Clientes;
* Perfil;
* Sair.

### `STOCK_KEEPER`

* Painel;
* Explorar;
* Obras;
* Perfil;
* Sair.

### `ADMINISTRATOR`

* Painel;
* Explorar;
* Obras;
* Clientes;
* Funcionários;
* Perfil;
* Sair.

Itens de versões futuras não devem aparecer como módulos funcionais na navegação da V1.

## 12. Painel por papel

A rota `/painel` deve usar um único template estrutural, com conteúdo baseado nas capacidades do usuário.

### Painel `USER`

* saudação;
* dados básicos da conta;
* acesso ao catálogo;
* acesso ao perfil.

### Painel `SELLER`

* consulta rápida do catálogo;
* acesso à gestão de clientes;
* resumo de pendências suportadas pelo backend.

### Painel `STOCK_KEEPER`

* total de obras;
* total de exemplares;
* quantidade disponível;
* atalhos para cadastrar obra e gerenciar acervo.

### Painel `ADMINISTRATOR`

* visão geral da V1;
* gestão de obras;
* gestão de clientes;
* gestão de funcionários;
* indicadores sustentados pelos endpoints existentes.

Não devem ser exibidas métricas fictícias como se fossem dados reais.

## 13. Operações críticas

As seguintes ações exigem confirmação explícita:

* inativar obra;
* inativar exemplar;
* inativar cliente;
* inativar funcionário;
* alterar papéis;
* converter destinação;
* remover acesso administrativo.

A confirmação deve:

* identificar o registro afetado;
* explicar o impacto;
* exigir justificativa quando a regra determinar;
* preservar foco acessível;
* apresentar sucesso somente após confirmação do backend.

## 14. Pendências obrigatórias de alinhamento

### 14.1 Cadastro PF/PJ

O documento prevê cadastro PF/PJ, mas o banco removeu `account_type`.

Até a decisão:

* o cadastro visual deve permanecer unificado;
* CPF, CNPJ e razão social não devem ser inventados;
* o requisito deve permanecer registrado como pendência;
* uma futura solução pode usar uma entidade de conta ou organização separada do usuário.

### 14.2 Acervo único por conta

O documento prevê acervo único por conta, mas o modelo precisa responder:

* qual entidade representa a conta?
* como PF e PJ são diferenciadas?
* quem é o proprietário do acervo?
* como funcionários são vinculados ao acervo?
* como obras e exemplares são isolados entre contas?
* o catálogo é global ou filtrado pela conta?

Até essa definição, o escopo visual deve representar o acervo administrativo como pertencente ao contexto da conta ativa, sem afirmar que esse isolamento já está implementado.

### 14.3 Cardinalidade dos papéis

O banco permite potencialmente múltiplos papéis por usuário.

Até que exista uma regra de papel único:

* a interface deve suportar vários papéis;
* as permissões devem ser combinadas;
* o menu deve refletir as capacidades efetivas;
* a documentação não deve afirmar que cada funcionário possui exatamente um papel.

### 14.4 Penalidades

Antes de permitir alteração de penalidade, devem ser definidos:

* quem pode aplicar;
* quem pode remover;
* justificativa;
* duração;
* histórico;
* impacto operacional.

Enquanto isso, `SELLER` deve apenas consultar a situação e `ADMINISTRATOR` só deve alterar quando houver endpoint e regra confirmados.

## 15. Critérios de aceite do escopo UX

A V1 estará coerente com os papéis quando:

* utilizar somente os quatro papéis oficiais;
* proteger rotas e operações no frontend e backend;
* apresentar navegação diferente por capacidade;
* permitir que o administrador herde as capacidades internas;
* impedir que o estoquista converta destinação sem autorização;
* restringir gestão de funcionários ao administrador;
* permitir que vendedor e administrador consultem clientes;
* diferenciar obra de exemplar;
* não exibir transações da V2 como funcionais;
* não exibir auditoria e notificações da V3;
* registrar PF/PJ e propriedade do acervo como pendências enquanto o banco não oferecer contrato suficiente;
* não simular persistência ou sucesso.
# Matriz de navegação operacional

| Papel | Item na navegação | Rota | Backend | Estado |
|---|---|---|---|---|
| Todos | Início / Explorar livros | `/`, `/explorar` | `/api/v1/catalog/*` | Funcional |
| `USER` | Meu painel | `/painel` | sessão de autenticação | Funcional |
| `SELLER` | Meu painel | `/painel` | sessão de autenticação | Funcional |
| `SELLER`, `ADMINISTRATOR` | Balcão (V2) | `/balcao` | `/api/v1/staff/*` (consultas e confirmações V2), `/api/v1/staff/clients/{id}/pendencies` | Funcional |
| `STOCK_KEEPER` | Cadastrar exemplar | `/gestao/acervo` | `/api/v1/books/*`, `/api/v1/copies/` | Funcional |
| `ADMINISTRATOR` | Cadastrar exemplar / Gestão de usuários | `/gestao/acervo`, `/gestao/usuarios` | acervo e usuários | Funcional |

Venda, empréstimo, devolução e reserva permanecem planejados. Como ainda não
possuem controllers e services transacionais completos, não aparecem como
botões operacionais na navbar nem nos cards do catálogo.

### Balcão V2 (`/balcao`) — Issue #122

Área operacional da V2, separada das operações transacionais antigas da V1 (que seguem como planejadas nesta matriz). Aparece na navbar e no painel apenas para `SELLER` e `ADMINISTRATOR`. A área segue os frames "Funcionário" do Figma (arquivo `gjM1ugpgfNOl5tjngzH65P`, página "LibStock — UX V2"): menu lateral de 250px (Painel, Acervo, Clientes, Empréstimos, Devoluções, Vendas, Reservas) que vira menu recolhível em telas menores. Cada alteração abre diálogo de confirmação, bloqueia envio duplicado e recarrega a lista após a resposta do backend. Cliente inelegível na frente da fila bloqueia a destinação; a interface explica o bloqueio e não pula a fila.

Mapa frame → rota (estado atual):

| Frame Figma | Rota | Situação |
| --- | --- | --- |
| Funcionário / Painel (3:133) | `/balcao/painel` | Conforme o frame; indicadores de `GET /api/v1/staff/dashboard` |
| Funcionário / Empréstimos / Início (20:2) | `/balcao/emprestimos` | Conforme o frame |
| Funcionário / Empréstimos / Solicitações de retirada (19:2) | `/balcao/emprestimos/solicitacoes` | Conforme o frame; "Fila desta obra" omitida (sem dado de fila de empréstimo no backend); notas "DEvs" do frame não são UI |
| Funcionário / Acervo (14:2) | `/balcao/acervo` | Conforme o frame: busca por título, autor ou ISBN, tabela e "Ver obra"; "+ Nova obra" (`/obras/nova`) só para quem o backend autoriza; nota "DEV" do frame não é UI |
| Funcionário / Acervo / Detalhes da obra (8:81) e Exemplares | `/balcao/acervo/:id` | Dados da obra, categoria e exemplares com finalidade/status reais; "Editar obra", "Salvar alteração" e "Inativar obra" só para STOCK_KEEPER/MANAGER/ADMINISTRATOR, com confirmação. Divergências: sem rádio Didático/Comercial (destinação é por exemplar), sem editar/converter exemplar nem reativação (decisões pendentes, seção 21); "Excluir exemplar" por linha, só para STOCK_KEEPER/ADMINISTRATOR (decisão delegada de 2026-10-03) |
| Funcionário / Empréstimos / Ativos (19:35) | `/balcao/emprestimos/ativos` | Conforme o frame: busca por cliente, e-mail, obra ou exemplar, contador "x ativos • x atrasados", tabela somente leitura (Cliente, Obra / exemplar, Retirada, Devolução, Status) e rodapé sobre pendência. Dados de `GET /api/v1/staff/loans`; atraso decidido pelo backend (regra V2). Os contadores refletem os itens listados (busca, filtro de cliente e limite de 50). Acrescenta o e-mail sob o nome e "há N dia(s)" no atrasado. |
| Funcionário / Devolução (3:219) | `/balcao/devolucoes` | Conforme o frame: "Registrar devolução", campo "Código do exemplar ou ISBN" (sem busca vazia), cartão com obra, exemplar, cliente e devolução prevista, "Confirmar devolução" com diálogo, bloqueio de envio duplicado e sucesso somente após 2xx (`POST /api/v1/staff/loans/{id}/confirm-return`); estados vazio, erro de consulta e erro de domínio (ex.: empréstimo já encerrado). Divergências: botão "Buscar" explícito; a trilha "← Devoluções" é texto, sem destino próprio; sem comprovante (fora de escopo); o ISBN pode listar vários exemplares emprestados da mesma obra, cada um com seu botão |
| Funcionário / Venda (3:238) | `/balcao/vendas` | Conforme o frame: "Registrar venda", campo "Código do exemplar, ISBN ou título" (`GET /api/v1/staff/copies`), cartão com obra, "Comercial • Disponível para venda", preço do exemplar e "Registrar venda" com diálogo, bloqueio de envio duplicado e sucesso somente após 2xx (`POST /api/v1/sales/`). Cartão de bloqueio para exemplar didático (sem a nota "LEMBRETE PARA OS DEVS", que não é interface) e cartão de indisponível. A venda é confirmada no ato e o exemplar fica vendido (decisão delegada de 2026-10-03, Issue #147/#149); o preço é sempre o do exemplar e a tela não o envia. Sucesso: "Venda registrada" com obra, exemplar vendido, total e número da venda retornados. Divergências: sem estoque antes e depois (o backend não o devolve); preço não editável e venda sem cliente; botão "Buscar" explícito; trilha em texto; sem comprovante |
| Complementos V2 · 02 Reservas de compra no balcão (4 telas) e 07 Estados de recuperação (referências: `png telas/paineis/07 — Complementos V2 · Fluxos para implementação.png`, seções 02 e 07; `png telas/referencias/05 — Estados & Modais.png`) | `/balcao/reservas`, `/balcao/reservas/:id?cliente=` | Item "Reservas" na sidebar. Lista "Reservas de compra" (fila por obra, busca por título, nome ou e-mail, "Atender X" e "Destinar exemplar a X" com confirmação) → "Atender reserva" (cliente, exemplar destinado, prazo só se persistido, "Código do exemplar" conferido contra o exemplar destinado do backend, "Conferir venda") → "Confirmar venda da reserva" (`POST /api/v1/staff/purchase-reservations/{id}/confirm-sale`, bloqueio de envio duplicado) → "Venda da reserva concluída" somente após 2xx. Estados "Nenhuma reserva encontrada" (busca sem resultado, "Limpar busca", "Voltar ao painel") e "Reserva fora do prazo" (apenas se o backend informar `expired`). Divergências: sem estoque antes/depois, sem ordinal "1ª" para a reserva com exemplar destinado, "Consultar outra obra" foca a busca; notas para devs não são UI; decisões em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21 |
| Complementos V2 · 03 Inclusão de exemplar, 04 Inativação de obra e 05 Exclusão de exemplar (referências: `png telas/paineis/07 — Complementos V2 · Fluxos para implementação.png`, seções 03 a 05) | `/balcao/acervo/:id/exemplares/novo`, `/balcao/acervo/:id` | "Novo exemplar" nos detalhes da obra (apenas papéis que o backend autoriza e obra ativa) → formulário Código e Finalidade (+ Preço de venda para Venda) → `POST /api/v1/copies/` → "Exemplar incluído" com quantidade antes/depois; código duplicado (409) mantém os dados e pede outro código. Inativação: modal "Inativar <obra>?" com "Situação verificada" e "Confirmar inativação" (`PATCH /api/v1/books/{id}`) → mensagem de obra inativada e cartão "Situação da obra"; se houver empréstimo em aberto, solicitação de retirada pendente ou reserva de compra aguardando/destinada, o backend responde 409 `book_has_active_operations` e a tela mostra "Inativação bloqueada" com "Vínculos encontrados" (contagens e vínculos devolvidos) e atalhos "Consultar empréstimos" e "Consultar reservas". Exclusão: botão "Excluir exemplar" por exemplar (só STOCK_KEEPER/ADMINISTRATOR; no balcão, ADMINISTRATOR), desabilitado com o motivo quando o status já indica bloqueio → modal "Excluir exemplar #código?" com "Confira o exemplar" e quantidade antes → depois (`DELETE /api/v1/copies/{id}`) → "Exemplar excluído" com a nova quantidade, ou "Exclusão bloqueada" com os motivos do 409 (`copy_not_available`, `copy_has_history`, `last_active_copy`). Divergências: preço de venda adicionado; os estados bloqueada/excluído aparecem na própria página da obra; o bloqueio de exemplar não mostra cliente nem data de devolução (o backend não os devolve); sem painel "Editando exemplar"; notas para devs não são UI; decisões em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21 |
| Complementos V2 · 06 Empréstimo direto no balcão (referências: `png telas/paineis/07 — Complementos V2 · Fluxos para implementação.png`, seção 06, proposta condicional; `png telas/referencias/05 — Estados & Modais.png`) | `/balcao/emprestimos/novo` | Acessível por "Novo empréstimo" em Empréstimos/Início e pelo card "Empréstimo" do Painel. Cliente (`GET /api/v1/staff/clients`) e exemplar didático livre (`GET /api/v1/staff/copies`) → "Revisar empréstimo" → "Confirmar empréstimo" (`POST /api/v1/loans/`, `SELLER`/`ADMINISTRATOR`, prazo calculado pelo backend) → "Empréstimo registrado" com `loan_date`/`due_date` retornados; "Empréstimo bloqueado" a partir dos erros de domínio reais (cliente inativo, com pendência ou inexistente; exemplar indisponível ou inexistente), com antecipação por `eligible`. Divergências: sem comprovante, sem CPF, sem prazo exibido antes do registro; prazo V1 x V2 não unificado (decisão pendente); decisões em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21 |
| Controle de pendências (referências: `png telas/telas/funcionario/Controle de pendências.png`, `04 — Administrador.png` tela 3; `png telas/referencias/05 — Estados & Modais.png`) | `/balcao/clientes` | Item "Clientes" da sidebar. Busca por nome ou e-mail (`GET /api/v1/staff/clients`) → cartão da situação (`GET /api/v1/staff/clients/{id}/pendencies`, somente leitura, regra V2): "Pendência ativa" com obra, exemplar, vencimento e dias de atraso, ou "Sem pendência"; atalhos Solicitações, Empréstimos ativos e Reservas filtrados pelo cliente. Estados de carregamento, vazio, erro com nova tentativa. Divergências: CPF não existe no modelo (limitação técnica, o placeholder diz só nome ou e-mail), lista de escolha para vários resultados, estado "Sem pendência" e avisos de penalizado/inativo não existem no desenho; notas para devs não são UI; decisões em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21 |
| Controle de pendências (8:69), Novo empréstimo (39:519 a 39:609) | `/balcao/clientes` | Funcionam com a implementação anterior dentro do novo layout; aguardando leitura dos frames |

#### Feedback e estados de recuperação do balcão — Issue #137

Referências: `png telas/referencias/01 - UX - Snackbars & Feedback.png` e Complementos V2, seção 07 ("Não foi possível salvar").

- Componente `app-snackbar` (variantes sucesso, erro, atenção e informação), hospedado no layout `/balcao`: sucesso e recusa de uma operação de escrita aparecem ali; bloqueios, decisões e telas de resultado (venda concluída, empréstimo registrado, exemplar incluído, reserva fora do prazo) continuam como estado/cartão, sem mensagem duplicada; confirmação destrutiva continua em diálogo.
- Acessibilidade: regiões vivas persistentes (`status` educada e `alert` assertiva para erros), sem mover o foco, botão "Fechar" e Esc. Sucesso e informação somem em 8 s (a referência não indica tempo); erro, atenção e mensagens com ação permanecem até serem fechadas.
- Falha de rede ou 5xx em escrita mostra "Não foi possível salvar" com "Atualizar consulta" e "Voltar"; não há reenvio automático nem botão que reenvie a escrita, porque o resultado pode ser incerto e o backend não é idempotente. A repetição é manual, após atualizar a consulta e confirmar de novo.
- Divergências: textos prontos da referência não usados quando divergem do comportamento real (ex.: a venda direta mostra os dados devolvidos pelo backend); a variante informação ainda não é usada por nenhuma tela do balcão.

Regras e decisões pendentes em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21.

### Telas do cliente: login, início e categoria — Issue #129

Referências: `png telas/paineis/02 — Cliente.png` (telas 1 a 3), `png telas/telas/cliente/Início & Acervo.png` e `png telas/telas/cliente/Ao selecionar uma categoria.png`.

| Frame | Rota | Endpoints | Situação |
| --- | --- | --- | --- |
| Cliente / Login (tela 1) | `/login` | `POST /api/v1/auth/login` | Conforme a referência (dois campos, "Entrar", "Criar conta"). "Esqueceu a senha?" segue desabilitado com "em breve": não há fluxo aprovado e a nota "DEV" da referência manda manter o fluxo atual |
| Cliente / Início & Acervo (tela 2) | `/` | `GET /api/v1/catalog/genres`, `GET /api/v1/catalog/featured-books`, `GET /api/v1/catalog/books` (busca) | Navbar com busca, Início, Explorar acervo, Meus empréstimos, Minhas reservas e menu do usuário; hero com o texto da referência e "Explorar livros" (vai às categorias); categorias em destaque; livros em destaque com Empréstimo disponível, Venda disponível ou Esgotado e "Ver detalhes" |
| Cliente / Ao selecionar uma categoria (tela 3) | `/generos/:slug` | `GET /api/v1/catalog/genres/{slug}/books?q=&page=`, `GET /api/v1/catalog/genres` | Trilha "Explorar acervo / categoria", título, subtítulo, busca "Buscar dentro de <categoria>" (título ou autor, consulta do backend), chips de categorias com a atual marcada, cartões e paginação; estados de carregamento, categoria inexistente, erro, vazio e "nenhum resultado" com "Limpar busca" |

Divergências e lacunas (detalhes em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21): chip "Mais" e "Ver todos" ausentes (sem endpoint de todas as categorias nem de acervo completo); "Todos" volta ao início; "Indisponível" aparece como "Esgotado"; "gênero" não é critério da busca global; o bloco de busca recolhível do início foi mantido; sem filtro por várias categorias. Dados das imagens são ilustrativos e notas para desenvolvedores não são interface.

### Telas do cliente: detalhes, reservas e empréstimos — Issue #130

Referências: `png telas/paineis/02 — Cliente.png` (telas 4 a 7), `png telas/paineis/07 — Complementos V2 · Fluxos para implementação.png` (seção 01) e `png telas/referencias/05 — Estados & Modais.png`.

| Frame | Rota | Endpoints | Situação |
| --- | --- | --- | --- |
| Detalhes do livro, Empréstimo expandido (tela 4) | `/livros/:id` | `GET /api/v1/catalog/books/{id}`, `POST /api/v1/loan-requests` | Conforme: data de retirada, devolução prevista calculada (somente leitura), "Confirmar solicitação"; Venda e Consulta local recolhidas. A primeira modalidade em que o cliente pode agir abre por padrão; quantidades no singular/plural ("1 exemplar disponível") |
| Detalhes do livro, Venda expandido (tela 5) | `/livros/:id` | `POST /api/v1/purchase-requests` | Conforme: data pretendida, "A compra será finalizada presencialmente no balcão", "Confirmar solicitação de compra" |
| Complementos 01-1: venda esgotada | `/livros/:id` (Venda) | `GET /catalog/books/{id}` (`can_reserve`) | "Venda · Esgotado — nenhum exemplar comercial disponível", aviso "Você pode entrar na fila de compra" e "Reservar compra", somente quando o backend informa `can_reserve` |
| Complementos 01-2: confirmar reserva | `/livros/:id` (etapa de confirmação) | nenhum até confirmar | Livro, cliente (nome e e-mail da sessão), modalidade e "Como funciona a fila"; "Confirmar reserva" ou "Voltar". Nada é criado antes de confirmar |
| Complementos 01-3: reserva registrada | `/livros/:id` (resultado) | `POST /api/v1/purchase-reservations` | Só após 2xx; mostra a posição devolvida pela API, "Ver minhas reservas" e snackbar de sucesso (componente compartilhado, hospedado na página) |
| Complementos 01-4: reserva bloqueada | `/livros/:id` (bloqueio) | erro `client_ineligible`; leitura `GET /api/v1/loans/me` | Mostra a mensagem do backend e, somente leitura, os empréstimos `OVERDUE` do próprio cliente ("Empréstimo de X · Exemplar #N", "Devolução prevista … · em atraso"); sem atraso listado, apenas a mensagem e a orientação de ir ao balcão. O mesmo bloqueio vale para solicitações de empréstimo e de compra |
| Minhas reservas (tela 6) | `/minhas-reservas` | `GET /api/v1/purchase-reservations/me` | Conforme: Aguardando disponibilidade (posição) e Disponível para retirada (exemplar, "Disponível desde"), nota "Compras concluídas não aparecem aqui." |
| Meus empréstimos (tela 7) | `/meus-emprestimos` | `GET /api/v1/loans/me` | Conforme: Aguardando retirada, Empréstimo ativo e Em atraso ("vencido há N dia(s)" no plural correto e orientação sobre a pendência) |

Feedback: sucesso só após 2xx; envio bloqueado enquanto há requisição em curso; erros de domínio (duplicidade, indisponível, inelegível) usam a mensagem e o código do backend e não geram snackbar de sucesso; duplicidade oferece o link para Meus empréstimos / Minhas reservas.

Divergências e lacunas (detalhes em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21): (1) "Retire até <data>" aparece somente quando `expires_at` existe; não há prazo aprovado, e a data de 23/09 da imagem é ilustrativa; (2) "Situação do cliente: apto — conta ativa e sem pendências" (01-2) não é exibida, porque não há consulta de elegibilidade do cliente; a elegibilidade é decidida pelo backend no envio; (3) a pendência de penalidade cadastrada sem empréstimo em atraso não tem consulta de detalhes para o cliente (lacuna); (4) as etapas de confirmar, registrada e bloqueada são estados da própria rota `/livros/:id`, sem rotas novas; (5) "Consulta local" segue não configurada e só mostra texto informativo se um dia estiver configurada; (6) o tipo de "Outras formas de acesso" de 01-1 não foi criado, pois repete as modalidades já exibidas. Dados das imagens são ilustrativos e notas para desenvolvedores não são interface.

### Gestão de usuários do administrador — Issue #131

Referências: `png telas/paineis/04 — Administrador.png` (telas 1 e 2), `png telas/recortes/admin_01.png`, `admin_02.png` e `png telas/telas/administrador/Detalhe e edição de usuário.png`.

| Frame | Rota | Endpoints | Situação |
| --- | --- | --- | --- |
| Gestão de usuários (admin_01) | `/gestao/usuarios` | `GET /api/v1/users?role=` | Colunas Usuário, E-mail, Perfil, Status e Ações (Ver / Editar; apenas Ver para inativos). Busca local por nome ou e-mail sobre a lista carregada; filtro por perfil mantido. Sem Inativar nem Excluir na lista |
| Sidebar com "Usuários" (admin_01) | item do menu lateral do balcão | nenhum | Item "Usuários" visível somente para `ADMINISTRATOR`, apontando para `/gestao/usuarios`; as rotas mantêm `authGuard` e `roleGuard` (`ADMINISTRATOR`) |
| Detalhe e edição de usuário (admin_02) | `/gestao/usuarios/:id/editar` | `GET /api/v1/users/{id}`, `PATCH /api/v1/users/{id}`, `PATCH /api/v1/users/{id}/inactivate`, `GET /api/v1/staff/clients/{id}/pendencies` | Nome, e-mail e Perfil editáveis; "Salvar alterações"; "Inativar usuário" abre o cartão "Inativar usuário?" (Cancelar / Confirmar inativação). Mudança de perfil também pede confirmação. Sucesso só após 2xx, botões bloqueados durante a requisição, erros de domínio no snackbar compartilhado |
| Detalhe somente leitura | `/gestao/usuarios/:id` | `GET /api/v1/users/{id}`, `GET /api/v1/staff/clients/{id}/pendencies` | Mesmos dados e a seção Pendências, com "Editar usuário" apenas para ativos |

Pendências (somente leitura): para usuários com perfil Cliente, usa a consulta V2 do balcão, que não sincroniza penalidade (o id do cliente coincide com o id do usuário): "Sem pendências ativas" ou, por empréstimo em atraso, obra, exemplar, vencimento e dias de atraso, mais o aviso de penalizado. Não usa a consulta V1 `/api/v1/clients/{id}/pendencies`, que grava penalidade. Para os demais perfis aparece "Pendências se aplicam somente a clientes."

Divergências e lacunas (detalhes em [BUSINESS_RULES.md](BUSINESS_RULES.md), seção 21): (1) CPF não existe no modelo: o campo e o termo "CPF" da busca não são exibidos (limitação técnica); (2) a referência usa uma única tela para detalhe e edição; as duas rotas existentes foram mantidas; (3) a página de gestão de usuários fica fora do layout do balcão (rota `/gestao/usuarios` existente), portanto a sidebar leva até ela mas não é exibida nela; (4) rótulos de perfil reais (Cliente, Vendedor, Estoquista, Administrador) em vez de "Funcionário"; (5) a referência não tem ação de penalidade manual; embora `PATCH /api/v1/clients/{id}/penalty` esteja aprovado na seção 20, não foi exposto. Dados das imagens são ilustrativos e notas para desenvolvedores não são interface.
