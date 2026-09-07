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
| T12 | Gestão de funcionários        | `/gestao/funcionarios`                            | `ADMINISTRATOR`                 |

Criação e edição reutilizam o mesmo template. Drawers, modais, confirmações e estados de erro não são contabilizados como telas independentes.

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

