# Migração e revisão do backlog — LibStock

## Objetivo

Este documento registra a migração do backlog do LibStock para uma estrutura orientada a histórias, preservando as Issues existentes, a rastreabilidade com a EAP e o mesmo GitHub Project.

A migração **não significa que todas as histórias estão aprovadas funcionalmente**. Ela organiza imediatamente o backlog por tipo, milestone, prioridade e tamanho; o Product Owner deve revisar os pontos de negócio ainda abertos depois da migração.

## Estrutura da migração

Cada card recebe uma ação no `analysis/migration-map.json`:

- `keep`: preserva título e body; associa milestone e campos de planejamento.
- `rewrite`: preserva o número da Issue, mas atualiza título e body com o arquivo em `stories/`.
- `split`: transforma a Issue original em EPIC e cria novas sub-issues para comportamentos independentes.

Configuração atual:

- Repositório: `yeslei/libstock`
- Project: `#5`
- Owner do Project: `yeslei`
- V1: 27 Issues
- V2: 18 Issues
- V3: 16 Issues
- Total: 61 Issues

Os Status atuais dos cards existentes são preservados. Novas sub-issues começam em `Backlog`.

## Milestones existentes

O script resolve automaticamente os títulos reais no GitHub a partir das chaves `V1`, `V2` e `V3` do mapa.

- V1 — núcleo operacional e proposta de gestão flexível de acervos.
- V2 — ampliação dos fluxos de circulação e interação.
- V3 — consolidação do produto e mecanismos de apoio.

## O que será alterado

### `keep`

- mantém título/body;
- associa milestone;
- preenche `Priority` e `Size` quando definidos;
- preserva Status e histórico.

### `rewrite`

- mantém o número da Issue;
- atualiza título;
- atualiza body usando `stories/<milestone>/...md`;
- associa milestone;
- preenche `Priority` e `Size`;
- preserva Status atual no Project.

### `split`

- mantém a Issue original e a transforma em EPIC;
- cria as histórias filhas;
- usa `Parent issue` para relacioná-las;
- associa as novas Issues ao mesmo milestone;
- adiciona as sub-issues ao Project #5;
- define `Priority`, `Size` e `Status=Backlog` para as novas sub-issues.

## Execução

Validar autenticação:

```bash
gh auth status
```

Executar dry-run de todo o backlog:

```bash
python migrate_backlog.py --dry-run
```

Aplicar todo o backlog:

```bash
python migrate_backlog.py --apply
```

É possível limitar por milestone ou Issue:

```bash
python migrate_backlog.py --milestone V1 --dry-run
python migrate_backlog.py --milestone V1 --apply
python migrate_backlog.py --issue 16 --dry-run
```

O script mantém:

- `analysis/migration-state.json`: registra sub-issues criadas para evitar duplicação em nova execução;
- `analysis/migration-result.json`: registra resultado e erros da última execução.

**Não apagar `migration-state.json` após uma aplicação parcial sem conferir as sub-issues já criadas.**

## Validação pós-migração

```bash
gh issue list \
  --repo yeslei/libstock \
  --state all \
  --limit 200 \
  --json number,title,milestone,state
```

```bash
gh project item-list 5 \
  --owner yeslei \
  --limit 200 \
  --format json
```

Conferir:

- Issues continuam no mesmo Project;
- milestone está correto;
- Status antigo foi preservado;
- `Priority` e `Size` estão preenchidos;
- EPICs possuem as sub-issues esperadas;
- nenhuma sub-issue foi criada em duplicidade;
- cards concluídos continuam concluídos.

---

# Revisão necessária pelo Product Owner

## Princípio

O PO deve separar três conceitos:

- **Estruturado**: card está organizado e corretamente associado ao roadmap.
- **Refinado**: comportamento e escopo estão compreendidos.
- **Ready**: não existe decisão de produto importante pendente para implementação.

Uma Issue pode ser migrada sem estar `Ready`.

## Ordem recomendada de revisão

1. V1 em `In progress`;
2. V1 em `Priorizado`;
3. demais User Stories da V1;
4. V2 antes de seu desenvolvimento;
5. V3 posteriormente.

## O que revisar em cada User Story

### Persona

- Quem executa ou recebe valor?
- Cliente, funcionário, administrador ou usuário genérico?

### Objetivo

- A ação representa uma necessidade de negócio?
- O card descreve resultado, e não apenas tarefa técnica?

### Benefício

- O `para` representa valor concreto?
- Remover benefícios genéricos como “executar essa funcionalidade”.

### Critérios de aceitação

- São observáveis e testáveis?
- Cobrem o fluxo principal?
- Cobrem erros importantes?
- Há comportamento ainda implícito?

### Regras de negócio

- A regra já foi aprovada?
- O card não está inventando regra por conveniência técnica?

### Permissões

- Qual papel pode executar a operação?
- Como ATTENDANT, STOCK_KEEPER, MANAGER e ADMINISTRATOR se relacionam às capacidades de negócio?

### Dependências

- As dependências herdadas da EAP continuam válidas?
- Há dependência funcional nova?

### Milestone

- A Issue realmente entrega parte do objetivo daquela versão?
- A decisão deve seguir o escopo do milestone, não apenas a numeração da EAP.

### Ready

- Há decisão funcional crítica em aberto?
- Se houver, manter em `Backlog` mesmo após a migração.

## Pontos já identificados para revisão do PO

### Controle de pendências do cliente

Definir o que é uma pendência e o que ela bloqueia:

- empréstimo vencido;
- devolução pendente;
- pagamento;
- reserva;
- outro tipo de bloqueio.

### Níveis de acesso

Os papéis existem tecnicamente, mas o PO deve validar a matriz de permissões:

- ATTENDANT;
- STOCK_KEEPER;
- MANAGER;
- ADMINISTRATOR.

### Conversão de categoria/destinação do acervo

Confirmar:

- alteração na obra ou no exemplar;
- conversão individual ou em lote;
- obrigatoriedade de preço ao migrar para comercial;
- comportamento de exemplares emprestados/reservados;
- necessidade de histórico;
- papéis autorizados.

### Sinalização Venda / Empréstimo / Esgotado

Confirmar:

- como cada sinalização é calculada;
- relação com disponibilidade dos exemplares;
- relação com modalidade configurada;
- significado exato de “esgotado”;
- possibilidade de múltiplas modalidades simultâneas.

### Home / Área Explorar

Confirmar:

- conteúdo mínimo da V1;
- dados exibidos;
- necessidade de autenticação;
- paginação;
- ordenação padrão;
- tratamento de acervo vazio;
- filtros obrigatórios.

### Obras

Confirmar regras de negócio para:

- campos obrigatórios;
- ISBN opcional/obrigatório;
- duplicidade de ISBN;
- autor;
- gênero;
- editora;
- edição;
- capa;
- ano;
- obras inativas.

### Exemplares

Confirmar:

- regra do código de barras;
- estado inicial;
- diferença operacional entre DIDACTIC e COMMERCIAL;
- obrigatoriedade de preço;
- mudança de destinação;
- estados que permitem edição/inativação.

### Consulta e disponibilidade

Confirmar:

- busca parcial;
- sensibilidade a maiúsculas/minúsculas;
- combinação de filtros;
- visibilidade de registros inativos;
- disponibilidade da obra versus disponibilidade do exemplar;
- dados mínimos retornados em Explorar.

## Definition of Ready sugerida

Uma User Story pode sair de `Backlog` para `Priorizado` quando:

- persona validada;
- objetivo e benefício compreendidos;
- critérios de aceitação testáveis;
- regras principais definidas;
- milestone confirmado;
- dependências identificadas;
- nenhuma questão funcional crítica em aberto;
- tamanho suficientemente pequeno para implementação.

## Definition of Done sugerida

Quando aplicável:

- critérios de aceitação atendidos;
- backend/frontend implementados;
- testes automatizados passando;
- integração validada;
- revisão de código concluída;
- documentação atualizada;
- PR aprovada e integrada.

## Rastreabilidade

Os dados originais da EAP devem continuar preservados nos corpos das Issues, incluindo, quando existentes:

- ID EAP;
- pacote principal;
- SP;
- dependências;
- responsável;
- apoio;
- horas previstas;
- custo previsto.

## Regra para decisões posteriores

Quando o PO alterar uma regra de negócio:

1. atualizar a Issue;
2. registrar a decisão nos critérios/regras;
3. revisar histórias dependentes;
4. não implementar alteração silenciosa apenas no código.

O backlog deve se tornar a referência compartilhada entre Produto, Desenvolvimento, QA e agentes de IA.
