# LibStock — Migração, Estruturação e Revisão do Backlog

## 1. Objetivo deste documento

Este README registra o processo de reorganização do backlog do projeto **LibStock** no GitHub, descreve o estado final da migração e define os pontos que ainda precisam ser revisados pelo Product Owner (PO) antes de cada item ser considerado pronto para desenvolvimento.

A migração teve como objetivo transformar o backlog existente em uma estrutura mais clara de:

- User Stories;
- itens técnicos;
- itens de QA;
- documentação;
- épicos;
- sub-issues;
- milestones V1, V2 e V3;
- campos de Project como `Priority`, `Size` e `Status`.

A reorganização preservou a rastreabilidade com a EAP e evitou a exclusão/recriação desnecessária de Issues já existentes.

> **Importante:** uma Issue estar migrada e estruturada no GitHub não significa que ela esteja automaticamente pronta para desenvolvimento. O PO ainda deve validar regras de negócio, critérios de aceite, dependências e decisões abertas.

## 2. Estado atual da migração

### 2.1. Migração das Issues

Responsável:

```text
migrate_issues_rest.py
```

Resultado:

```text
61 Issues originais processadas
0 erros
```

A etapa realizou:

- atualização de títulos;
- atualização de bodies;
- associação aos milestones;
- manutenção da rastreabilidade das Issues originais;
- transformação de duas Issues em épicos;
- criação de quatro sub-issues;
- associação parent/sub-issue;
- preservação do histórico existente.

Foram mantidas as Issues já concluídas sem reabertura desnecessária.

### 2.2. Sincronização do GitHub Project

Responsável:

```text
sync_project.py
```

Resultado validado em dry-run:

```text
61 Issues originais processadas
4 children processadas
65 Project items encontrados
0 erros
```

A sincronização do Project é responsável exclusivamente por:

- `Priority`;
- `Size`;
- inclusão das children no GitHub Project;
- `Status=Backlog` para children novas;
- preservação do Status das Issues originais.

O script não altera novamente:

- título;
- body;
- milestone;
- labels;
- assignees;
- estado open/closed;
- relação parent/sub-issue.

## 3. Estrutura final do backlog

O backlog possui:

```text
61 Issues originais
+ 4 sub-issues
= 65 Issues/cards
```

Distribuição lógica das 61 Issues originais:

| Milestone | Issues originais |
|---|---:|
| V1 | 27 |
| V2 | 18 |
| V3 | 16 |
| **Total** | **61** |

Após a criação das quatro children na V1:

| Milestone | Total físico esperado |
|---|---:|
| V1 | 31 |
| V2 | 18 |
| V3 | 16 |
| **Total** | **65** |

## 4. Milestones

### V1

**Título**

> V1 - Rodada 1: Estabelecer o núcleo operacional da plataforma e demonstrar sua proposta de gestão flexível de acervos.

**Escopo geral**

- preparação;
- autenticação e usuários;
- perfis e papéis;
- cadastro e manutenção de obras;
- cadastro e manutenção de exemplares;
- busca inicial;
- validações associadas;
- funcionalidades iniciais da página principal;
- QA associado à primeira rodada.

### V2

**Título**

> V2 - Ampliar os fluxos de circulação e interação entre os usuários.

**Escopo geral**

- empréstimos;
- devoluções;
- atualização de status de exemplares;
- comprovantes;
- vendas;
- validação de disponibilidade;
- reservas;
- fila de reservas;
- notificações de disponibilidade;
- QA dos fluxos de circulação.

### V3

**Título**

> V3 - Consolidar o produto e seus mecanismos de apoio.

**Escopo geral**

- atraso;
- alertas;
- lembretes;
- canais de notificação;
- permissões avançadas;
- reautenticação;
- auditoria;
- backup;
- segurança;
- requisitos não funcionais;
- integração;
- correções;
- testes de aceitação;
- preparação da versão final;
- documentação de entrega.

## 5. Observação sobre os contadores visuais dos milestones

Durante a validação foi identificada uma inconsistência entre:

- a associação real das Issues aos milestones;
- os contadores agregados apresentados pela tela de Milestones do GitHub.

Exemplo observado:

```text
Issue #28
milestone.number = 2
```

e a consulta filtrada por milestone retornou corretamente as 18 Issues da V2.

Da mesma forma:

```text
V3 = 16 Issues
```

foi confirmado pela listagem REST.

Apesar disso, o endpoint agregado de milestone e a interface visual chegaram a mostrar:

```text
V2: 0 open / 0 closed
V3: 0 open / 0 closed
```

Portanto, para auditoria da migração, deve-se considerar como fonte de verdade a associação individual de cada Issue e as consultas filtradas por milestone, e não somente os contadores visuais da página de milestones.

## 6. Issues transformadas em EPIC

### #12 — Consultar e manter dados de usuários

Estrutura:

```text
#12 [EPIC] Consultar e manter dados de usuários
├── [US] Consultar usuário
└── [US] Atualizar dados de usuário
```

As duas funcionalidades foram separadas por representarem comportamentos distintos e passíveis de validação independente.

### #18 — Consultar e manter obras

Estrutura:

```text
#18 [EPIC] Consultar e manter obras
├── [US] Consultar obra
└── [US] Atualizar obra
```

Assim como no caso anterior, consulta e atualização foram separadas para melhorar estimativa, rastreabilidade e definição de critérios de aceite.

## 7. Tipos utilizados

O backlog foi reorganizado semanticamente com os seguintes tipos:

```text
[US]   User Story
[EPIC] Epic
[TECH] Atividade técnica
[QA]   Teste / validação
[DOC]  Documentação
```

Distribuição da classificação original do mapa de migração:

```text
41 user stories
9 QA
8 technical
2 epics
1 documentation
```

## 8. Status

O processo de migração preservou o Status das Issues já existentes no GitHub Project.

Exemplos de estados preservados:

- `Backlog`;
- `Priorizado`;
- `In progress`;
- `In review`;
- `Done`.

Nenhum script deve redefinir em massa as Issues existentes para `Backlog`.

Regra adotada:

```text
Issue existente
→ Status preservado

Child nova
→ Status = Backlog
```

## 9. Priority

O campo `Priority` utiliza:

```text
P0
P1
P2
```

Interpretação adotada durante a reorganização:

- **P0:** prioridade crítica para o núcleo funcional;
- **P1:** prioridade importante para evolução do produto;
- **P2:** prioridade posterior, consolidação ou suporte.

A prioridade atual foi definida como base inicial de planejamento e ainda pode ser revisada pelo PO.

## 10. Size

O campo `Size` utiliza:

```text
XS
S
M
L
XL
```

A estimativa representa tamanho relativo e não deve ser interpretada diretamente como horas.

O PO e a equipe técnica podem revisar `Size` após refinamento das regras de negócio.

## 11. Rastreabilidade com a EAP

A reorganização do backlog não elimina a estrutura de EAP utilizada no planejamento do projeto.

As labels e agrupamentos da EAP devem continuar servindo como mecanismo de rastreabilidade entre:

```text
EAP
↓
Pacote de trabalho
↓
Issue / Epic / User Story
↓
Milestone
↓
Implementação
```

Pacotes de trabalho considerados na reorganização:

- preparação;
- usuários e acesso;
- catálogo;
- busca no catálogo;
- empréstimos e devoluções;
- vendas;
- reservas de compra;
- alertas e notificações;
- segurança e auditoria;
- testes e validação;
- integração e entrega.

## 12. O que o PO deve revisar

A migração estruturou os cards, mas não substitui o refinamento funcional.

Cada User Story deve ser revisada pelo PO considerando os pontos abaixo.

### 12.1. Persona

Confirmar quem executa ou recebe valor da funcionalidade.

Exemplos:

- cliente;
- funcionário;
- atendente;
- estoquista;
- gerente;
- administrador;
- usuário não autenticado.

Evitar personas genéricas quando a permissão depende diretamente do perfil.

### 12.2. Objetivo

O objetivo deve descrever claramente o que o usuário deseja realizar.

Evitar objetivos que misturem múltiplos comportamentos independentes.

Quando necessário, a Issue deve ser novamente dividida.

### 12.3. Benefício

O benefício deve responder:

> Qual valor a funcionalidade entrega para o usuário ou para o negócio?

Benefícios genéricos devem ser refinados.

### 12.4. Critérios de aceite

Os critérios devem ser:

- verificáveis;
- objetivos;
- independentes da implementação sempre que possível;
- suficientes para orientar testes;
- coerentes com as regras de negócio.

Evitar critérios como:

```text
A funcionalidade deve funcionar corretamente.
```

Preferir:

```text
Dado um exemplar disponível,
quando um empréstimo válido for registrado,
então o exemplar deve passar para o estado BORROWED.
```

### 12.5. Regras de negócio

Regras críticas devem estar explícitas no card.

Exemplos:

- quem pode realizar a operação;
- validações;
- limites;
- estados permitidos;
- transições de estado;
- tratamento de conflitos;
- restrições de estoque;
- regras de disponibilidade;
- situações de erro.

### 12.6. Permissões

Confirmar a matriz de acesso por papel.

Papéis atualmente previstos no domínio:

```text
ATTENDANT
STOCK_KEEPER
MANAGER
ADMINISTRATOR
```

A existência desses papéis no banco não significa que a autorização já esteja implementada.

O PO deve validar quais papéis têm acesso a cada funcionalidade.

### 12.7. Dependências

Cada Story deve informar dependências funcionais ou técnicas relevantes.

Exemplo:

```text
Cadastrar exemplar
depende de
Cadastrar obra
```

Ou:

```text
Registrar venda
depende de
Validar disponibilidade
```

### 12.8. Milestone

O PO deve confirmar se a Story realmente pertence à versão atribuída.

Especial atenção deve ser dada a funcionalidades que foram movidas durante a migração, principalmente os fluxos de empréstimo, devolução, venda e reserva.

## 13. Pontos específicos que exigem validação do PO

### 13.1. Cliente pendente

Revisar o comportamento relacionado ao estado ou situação de cliente pendente.

Definir:

- o que caracteriza pendência;
- quais operações são bloqueadas;
- como a pendência é removida;
- quem pode alterar essa situação.

### 13.2. Matriz de acesso

Definir explicitamente quais operações podem ser executadas por:

- atendente;
- estoquista;
- gerente;
- administrador.

A regra precisa ser consolidada antes da implementação completa de autorização.

### 13.3. Categoria e destinação — #22

Revisar a regra de alteração entre categorias/destinações.

O modelo atual prevê para exemplares:

```text
DIDACTIC
COMMERCIAL
```

O PO deve definir:

- se a destinação pode ser alterada após cadastro;
- em quais situações;
- impactos sobre empréstimos;
- impactos sobre vendas;
- impacto sobre preço.

### 13.4. Disponibilidade — #27

Definir de forma inequívoca o que significa uma obra ou exemplar estar disponível.

O domínio possui estados como:

```text
AVAILABLE
BORROWED
SOLD
RESERVED
INACTIVE
```

O PO deve definir como esses estados afetam:

- busca;
- página inicial;
- empréstimo;
- venda;
- reserva.

### 13.5. Página inicial / Explore — #66

Revisar o escopo de:

```text
[US] Visualizar acervos disponíveis na página inicial
```

Definir:

- quais itens aparecem;
- filtros;
- ordenação;
- quantidade;
- paginação;
- diferença entre Home e Explore;
- comportamento para usuário não autenticado.

### 13.6. Cadastro de obras

Confirmar:

- campos obrigatórios;
- tratamento de ISBN duplicado;
- possibilidade de obra sem ISBN;
- ano de publicação;
- edição;
- autor;
- gênero;
- editora;
- capa;
- inativação.

### 13.7. Cadastro de exemplares

Confirmar:

- obrigatoriedade de código de barras;
- unicidade;
- estado inicial;
- destinação inicial;
- condição física;
- preço obrigatório para exemplar comercial;
- regras de inativação.

### 13.8. Busca

Definir:

- busca por título;
- autor;
- ISBN;
- gênero;
- editora;
- disponibilidade;
- diferença entre disponibilidade de obra e disponibilidade de exemplar;
- ordenação;
- paginação.

### 13.9. Empréstimos

Revisar:

- critérios para cliente apto;
- quantidade máxima de empréstimos;
- prazo;
- cálculo de devolução;
- renovação, caso exista;
- devolução antecipada;
- atraso;
- bloqueios;
- comprovante digital.

### 13.10. Vendas

Definir:

- quem pode vender;
- quais exemplares podem ser vendidos;
- impossibilidade de venda de exemplar didático;
- disponibilidade;
- estoque;
- preço;
- cancelamento;
- efeitos sobre estado do exemplar.

### 13.11. Reservas

Definir detalhadamente:

- entrada na fila;
- ordem da fila;
- expiração;
- cancelamento;
- reserva de compra;
- reserva de exemplar;
- comportamento quando item fica disponível;
- prazo após notificação.

### 13.12. Notificações

Confirmar:

- canais disponíveis;
- canal padrão;
- eventos que geram notificação;
- reenvio;
- falhas de envio;
- opt-in/opt-out;
- lembrete de devolução;
- disponibilidade de reserva.

### 13.13. Auditoria

Definir:

- quais operações devem ser auditadas;
- quais informações serão armazenadas;
- quem pode consultar logs;
- tempo de retenção;
- tratamento de dados sensíveis;
- conceito de imutabilidade dos logs.

### 13.14. Backup

Definir:

- frequência;
- retenção;
- restauração;
- responsável;
- ambiente;
- evidência de execução.

## 14. Definition of Ready

Uma Issue só deve ser considerada **Ready** quando possuir, no mínimo:

- [ ] persona definida;
- [ ] objetivo claro;
- [ ] benefício explícito;
- [ ] critérios de aceite verificáveis;
- [ ] regras de negócio necessárias;
- [ ] permissões definidas;
- [ ] milestone confirmado;
- [ ] dependências identificadas;
- [ ] tamanho administrável;
- [ ] nenhuma decisão crítica de produto em aberto;
- [ ] contexto suficiente para desenvolvimento e QA.

## 15. Migrado não significa Ready

Os estados devem ser tratados separadamente.

```text
MIGRADO
=
card reorganizado estruturalmente no GitHub
```

```text
READY
=
card refinado e aprovado para desenvolvimento
```

Portanto:

> Todo card Ready pode estar migrado, mas nem todo card migrado está Ready.

Essa distinção deve ser mantida durante o refinamento do backlog.

## 16. Definition of Done sugerida

Uma funcionalidade pode ser considerada concluída quando:

- [ ] implementação finalizada;
- [ ] critérios de aceite atendidos;
- [ ] testes automatizados relevantes executados;
- [ ] testes manuais necessários executados;
- [ ] autorização validada;
- [ ] tratamento de erros implementado;
- [ ] documentação atualizada quando necessário;
- [ ] migrations versionadas quando aplicável;
- [ ] revisão de código concluída;
- [ ] branch integrada;
- [ ] funcionalidade validada no ambiente correspondente.

## 17. Pontos editoriais a revisar

Os bodies foram gerados automaticamente como base de migração.

Por isso, alguns cards ainda podem apresentar:

- critérios de aceite genéricos;
- construções repetitivas;
- pequenos erros de digitação;
- formatação Markdown inconsistente;
- textos que precisam de maior precisão de negócio.

Exemplos observados durante a migração:

```text
deerro
deverespeitar
-[ ]
Responsavel|
```

Esses problemas não justificaram bloquear a migração, mas devem ser corrigidos no refinamento editorial.

Também deve ser verificado o título efetivamente cadastrado no GitHub para evitar pequenas inconsistências de digitação nos milestones.

## 18. Arquivos da migração

Estrutura utilizada:

```text
backlog-migration/
├── input/
│   ├── issues.json
│   ├── project-items.json
│   └── project-fields.json
│
├── analysis/
│   ├── migration-map.json
│   ├── issues-rest-migration-state.json
│   ├── issues-rest-migration-result.json
│   └── project-sync-result.json
│
├── stories/
│   ├── V1/
│   ├── V2/
│   └── V3/
│
├── generate_migration_map.py
├── generate_story_bodies.py
├── migrate_issues_rest.py
├── sync_project.py
└── README_BACKLOG_MIGRATION.md
```

## 19. Papel de cada script

### generate_migration_map.py

Responsável por gerar o mapa de transformação das Issues.

Define, entre outros:

- tipo;
- ação;
- milestone;
- prioridade;
- tamanho;
- splits.

### generate_story_bodies.py

Responsável por gerar os arquivos Markdown utilizados como body das Issues.

Saída:

```text
stories/V1/
stories/V2/
stories/V3/
```

### migrate_issues_rest.py

Responsável por alterações nas Issues através da API REST.

Executa:

- rewrite;
- keep;
- split;
- criação de children;
- relação parent/sub-issue;
- milestone;
- title;
- body.

Não deve ser utilizado para alterar campos do GitHub Project.

### sync_project.py

Responsável exclusivamente pelos metadados do GitHub Project.

Executa:

- Priority;
- Size;
- inclusão de children;
- Status inicial das children.

Preserva o Status das Issues originais.

## 20. Estratégia de segurança da migração

Princípios adotados:

1. validar antes de escrever;
2. separar REST de GraphQL;
3. não recriar Issues existentes;
4. preservar números e histórico;
5. preservar Status;
6. tornar scripts idempotentes;
7. evitar mutations desnecessárias;
8. permitir `--dry-run`;
9. manter arquivos de estado;
10. permitir retomada após falha.

## 21. Rate limit e GraphQL

A migração das Issues foi separada do GitHub Project porque o endpoint GraphQL apresentou períodos de rate limit e instabilidade.

Assim:

```text
REST
→ fonte principal para Issues

GraphQL
→ utilizado somente para GitHub Projects v2
```

O `sync_project.py` verifica o rate limit GraphQL antes de iniciar alterações.

Essa separação evita que uma indisponibilidade do GraphQL comprometa a estrutura funcional do backlog.

## 22. Critérios de auditoria final

A migração pode ser considerada estruturalmente concluída quando:

```text
Issues originais             61
Children                      4
Total                         65

V1 físico                     31
V2 físico                     18
V3 físico                     16

Issues sem milestone           0

Issues originais no Project   61
Children no Project            4

Priority ausente               0
Size ausente                   0

Status originais alterados
indevidamente                  0

Children fora do Backlog       0

Erros de sincronização         0
```

## 23. Próximo passo do projeto

Após a migração técnica, o backlog entra em fase de **refinamento funcional**.

Fluxo recomendado:

```text
Backlog migrado
↓
Revisão do PO
↓
Validação de regras de negócio
↓
Validação de critérios de aceite
↓
Validação de dependências
↓
Definition of Ready
↓
Priorização da Sprint / Rodada
↓
Desenvolvimento
↓
QA
↓
Done
```

Para a execução imediata do projeto, a prioridade deve ser revisar primeiro as Stories da **V1**, principalmente as que estão `Priorizado` ou `In progress`.

## 24. Conclusão

A reorganização do backlog do LibStock estabeleceu uma base consistente para o desenvolvimento incremental do produto.

O backlog agora possui:

- rastreabilidade preservada;
- organização por versões;
- separação entre negócio, técnica, QA e documentação;
- EPICs para funcionalidades compostas;
- sub-issues para comportamentos independentes;
- prioridade e tamanho;
- preservação do histórico;
- suporte a refinamento progressivo.

A partir deste ponto, o foco deixa de ser a migração estrutural e passa a ser a **qualidade do refinamento das User Stories**.

O PO deve tratar este README como guia de revisão e registrar decisões diretamente nos cards correspondentes, garantindo que as Stories estejam suficientemente maduras antes de entrarem em desenvolvimento.
