# Plano de implementação — atualização do status do exemplar

## Execução posterior ao planejamento

O usuário aprovou edição manual restrita AVAILABLE ↔ INACTIVE, preservando
`is_active`. A implementação inclui PATCH autenticado, funcionário ativo,
pré-condição por `updated_at`, lock, auditoria e ação com confirmação no acervo.
As demais seções preservam o diagnóstico original e suas propostas; as regras
vigentes da entrega estão em `BUSINESS_RULES.md`, seção da issue #31.

Validação final da implementação:

- Backend: 285 testes passaram em PostgreSQL descartável provisionado por Alembic,
  incluindo leitura/PATCH/releitura HTTP, rollback real e duas sessões concorrentes.
- Alembic: check sem diferenças; upgrade head, downgrade -1 e upgrade head passaram.
- Frontend: build passou; aviso preexistente de orçamento CSS do catálogo (60 bytes).
- Angular: 71 testes das áreas afetadas passaram. A suíte completa executou 103
  testes, com 101 sucessos e duas falhas em `UserManagementComponent`: os testes
  procuram botões Excluir/Inativar que não existem no template atual, não alterado
  nesta entrega. O launcher Chromium Snap também registrou falha ao encerrar;
  não considerar a execução completa como verde.
- Um fixture antigo de `BookService.update` foi corrigido para usar `BookDetail`,
  com `cover_url` e `copies`, permitindo a compilação da suíte Angular.
- Ambiente disponível: Python 3.14 e PostgreSQL 18; a documentação declara Python
  3.12 e PostgreSQL 17. A matriz declarada ainda deve ser validada no CI.
- Não houve alteração estrutural, publicação ou criação/merge de PR.

## Rastreabilidade e diagnóstico

- Issue: [#31](https://github.com/yeslei/libstock/issues/31), aberta na consulta.
- EAP: `1.5.4`, pacote Gestão de Empréstimos e Devoluções; V2, P1, S, 3 SP.
- Base local examinada: commit `340ae8b`; árvore de trabalho inicialmente limpa.
- Dependência `1.5.1`: [#28 — Registro de empréstimo](https://github.com/yeslei/libstock/issues/28), fechada; backend presente, checklist de frontend ainda incompleto.
- Dependência `1.3.6`: [#21 — Controle de quantidade de exemplares](https://github.com/yeslei/libstock/issues/21), fechada; cadastro em lote presente, checklist de integração/frontend ainda incompleto.
- Fechamento de issue não comprova, sozinho, atendimento integral da DoD.

Este documento é um plano. As propostas abaixo não constituem regras de negócio aprovadas nem implementação da funcionalidade.

## Estado atual verificado

| Área | Evidência no repositório | Consequência para a entrega |
|---|---|---|
| Modelo | `backend/app/models/domain.py`: `Copy`, enum de cinco estados, `is_active`, timestamps, barcode único e índices | Reutilizar a entidade; atualizar status não exige, por si só, nova tabela ou enum |
| API de exemplares | `copy_controller.py`: POST individual e `/batch`; schemas e service de criação | Não existe PATCH específico de status |
| Consulta interna | `GET /api/v1/books/{book_id}` retorna exemplares; `BookRepository.get_with_copies` carrega a relação | Reutilizar a consulta para seleção e verificação do resultado |
| Interface | `stock-management.component` pesquisa obras e exibe código, destinação e status dos exemplares | Há ponto de integração para a ação, mas não há edição de status |
| Circulação | Migration `0005`: `apply_loan_copy_state` muda para BORROWED ao emprestar e AVAILABLE ao devolver/cancelar; repository de devolução também atribui AVAILABLE | A atualização automática já existe em parte; não duplicar operações de circulação em um PATCH genérico |
| Integridade | `guard_copy_integrity`, criado em `0005` e substituído em `0007`, exige empréstimo aberto para BORROWED e venda confirmada para SOLD | Service deve antecipar as restrições, mantendo proteção no PostgreSQL |
| Auditoria | Trigger `audit_inventory_change` exige `libstock.employee_id`, grava valores anterior/novo; repository de exemplares já configura o ator | Reutilizar contexto transacional e auditoria existentes |
| Autorização | `require_roles` verifica papel e usuário ativo; `CopyRepository.is_employee` só verifica existência do funcionário | Nova operação deve validar também atividade do perfil do funcionário |
| Documentação | `BUSINESS_RULES.md` enumera estados, mas exige documentar transições antes de implementá-las | Matriz de transições manuais ainda é decisão pendente |

Os estados atuais são AVAILABLE, BORROWED, RESERVED, SOLD e INACTIVE. A existência de um valor no enum não autoriza uma transição manual para ele.

### Classificação dos achados

- **Regra aprovada/implementada:** autenticação e autorização no backend, consistência transacional, identificação do funcionário, estados condicionados às operações de circulação e restrições persistentes existentes.
- **Funcionalidade planejada:** atualização manual do status pelo responsável do acervo. Sua ausência não é classificada como defeito da versão atual.
- **Decisão pendente:** alcance desta história, transições manuais, papéis específicos e relação entre INACTIVE e `is_active`.
- **Limitação técnica verificada:** PostgreSQL local indisponível durante a validação. Não foi possível comprovar os fluxos persistentes contra o banco.
- **Defeito confirmado da nova funcionalidade:** nenhum, pois ela ainda não está implementada. Há um achado estático diretamente relacionado à auditoria da devolução: o controller recebe o usuário atual, mas não o passa ao service; o trigger configura como ator o funcionário do empréstimo. Testar devolução por outro funcionário e corrigir a atribuição se a entrega abranger esse fluxo.

## Decisões necessárias antes de implementar as transições

1. **Escopo:** confirmar se #31 pretende completar a atualização automática em empréstimos/devoluções ou incluir edição manual no acervo. A EAP indica circulação; o texto da história não define uma matriz manual. O plano abaixo propõe edição manual restrita, condicionada a essa definição. Se o escopo for apenas automático, concentrar a entrega na integração, auditoria, testes reais e feedback do fluxo existente, sem criar um PATCH genérico.
2. **Matriz manual:** proposta inicial para avaliação: AVAILABLE → INACTIVE e INACTIVE → AVAILABLE. BORROWED e SOLD continuam controlados por suas operações; RESERVED depende de definição própria. Não implementar reservas, confirmação de venda ou cancelamento de empréstimo como efeito colateral.
3. **Atividade:** definir se INACTIVE altera `is_active` ou apenas a disponibilidade operacional. Os campos são independentes hoje. Se houver desativação, considerar a constraint que exige exemplar ativo para obra ativa; rejeitar conflitos com mensagem explícita, sem desativar a obra automaticamente. Definir também condições de reativação de exemplar e de sua obra.
4. **Papéis:** proposta de STOCK_KEEPER e ADMINISTRATOR, seguindo o cadastro e consulta interna. SELLER não recebe edição manual por inferência de sua permissão de circulação.
5. **Repetição e concorrência:** proposta de sucesso sem nova alteração/auditoria para solicitação do mesmo estado quando a pré-condição de versão ainda é válida; estado desatualizado retorna conflito. Definir se será exigida justificativa; não adicionar esse requisito por suposição.

Registrar as decisões em `docs/BUSINESS_RULES.md` como PENDING até confirmação e APPROVED após definição. Informar versão-alvo, atores, pré-condições, transições, auditoria e testes. Só marcar IMPLEMENTED após validar a entrega.

## Sequência de implementação proposta

### 1. Fechar contrato e critérios verificáveis

- Formalizar as decisões acima e uma tabela completa de origem/destino: permitido, proibido ou exclusivo da circulação.
- Reaproveitar consulta interna existente e definir o acesso a exemplares inativos. A busca atual usa o catálogo público; obras sem visibilidade no catálogo não serão localizáveis por ela. Se a regra exigir esse acesso, incluir uma consulta interna mínima autenticada, sem ampliar a exposição pública.
- Contrato proposto: `PATCH /api/v1/copies/{copy_id}/status`, com ID positivo, `status` obrigatório e rejeição de campos extras. Não aceitar ator, preço, destinação ou `is_active` arbitrariamente no payload.
- Proposta técnica para evitar sobrescrita de tela antiga: enviar `expected_updated_at` retornado na leitura e comparar sob lock. Expor o timestamp nos schemas internos necessários; serializar com precisão e fuso compatíveis. O campo já existe no modelo. O lock sozinho não detecta uma intenção baseada em leitura antiga.
- Responder 200 com o exemplar confirmado e timestamp atualizado; 422 para payload inválido; 401 sem autenticação; 403 sem papel, usuário/perfil inativo ou vínculo funcional; 404 inexistente; 409 para transição proibida, versão desatualizada ou conflito de integridade conhecido; 500 para falha inesperada de persistência.
- Criar códigos estáveis, por exemplo `copy_not_found`, `copy_transition_not_allowed`, `copy_state_conflict` e `copy_update_persistence_error`, seguindo `ApplicationError`. Os nomes são proposta de contrato.

### 2. Repository, service e endpoint

- `copy_repository.py`: consultar exemplar com `SELECT ... FOR UPDATE`; consultar funcionário/perfil ativo e vínculos relevantes; atualizar e executar flush sem commit interno. Manter acesso SQL nesta camada.
- `copy_service.py`: validar ator, obter lock, conferir versão e transição, validar vínculos de circulação, configurar ator da auditoria e persistir na mesma transação.
- Efetuar rollback em falhas de validação/persistência; garantir que sucesso só seja retornado depois do commit, inclusive quando constraints diferidas falharem na confirmação.
- Mapear conflitos conhecidos pelos identificadores/condições de banco adequados. Não reutilizar a mensagem de barcode duplicado para toda falha de status, nem converter indiscriminadamente qualquer erro SQL em 409.
- `copy_schema.py`: adicionar schema específico de atualização e ajustar resposta interna para concorrência, preservando contratos existentes.
- `copy_controller.py`: declarar autenticação, papéis e schemas explicitamente; delegar ao service e obter ator da sessão autenticada.
- Analisar a ordem de locks usada na circulação: devolução já bloqueia empréstimo antes do exemplar. Evitar introduzir ordem inversa; testar disputa com empréstimo, devolução e venda.

### 3. Banco e auditoria

- Preservar enum, timestamps, triggers e constraints existentes. Não criar migration apenas para disponibilizar uma rota.
- Se a matriz aprovada exigir novas invariantes estruturais ou alteração de trigger, criar nova migration reversível; nunca editar as migrations aplicadas `0005`/`0007`.
- Inspecionar dados incompatíveis antes de aplicar novas constraints, com tratamento explícito; não corrigir estados silenciosamente.
- Validar auditoria real: funcionário executante, valor anterior/novo, atomicidade e ausência de registro persistente após rollback.
- Na circulação, se incluída no escopo, transmitir o funcionário executante na devolução e ajustar o mecanismo de auditoria por nova migration quando necessário, sem apagar o funcionário original do empréstimo.
- Não criar nova entidade de histórico: já existe `audit_logs`.

### 4. Interface Angular

- Integrar ação por exemplar em `frontend/src/app/features/stock/stock-management`, mostrando código de barras e estado atual.
- Estender `features/copies/services/copy.service.ts` e modelos com PATCH, resposta e pré-condição de concorrência.
- Oferecer somente destinos da matriz aprovada; validação no frontend não substitui service e banco.
- Bloquear reenvio enquanto salva, preservar dados em erro e exibir feedback acessível de sucesso/erro.
- Em 409, recarregar estado atual e informar conflito; não repetir a mutação automaticamente.
- Após sucesso, atualizar a lista pelo retorno confirmado e reconsultar a obra/disponibilidade quando necessário. O usuário deve conseguir recarregar a página e verificar a persistência.
- Reutilizar guards existentes e testar ocultação da ação para não autorizados.

### 5. Testes e aceite

| Critério | Evidência exigida |
|---|---|
| Fluxo disponível ao autorizado | HTTP real com autenticação, papéis permitidos e negativos; vínculo funcional ausente; usuário e perfil inativos; ação na interface |
| Obrigatórios e entradas inválidas | Status ausente/nulo/desconhecido, ID inválido, campos extras e pré-condição de concorrência inválida |
| Resultado persistido | PATCH e nova leitura retornam estado confirmado; recarga da interface preserva resultado |
| Recurso inexistente | 404 com código estável |
| Regras de estado | Todas as transições da matriz; repetição; empréstimo aberto; venda confirmada; reserva conforme decisão; atividade da obra e exemplar |
| Atomicidade | Falha de flush, commit ou auditoria deixa status, atividade e histórico sem alterações parciais |
| Concorrência | Duas sessões PostgreSQL disputando o mesmo exemplar e disputa com circulação; sem sobrescrita silenciosa nem estado incompatível |
| Repository e banco | Testes com PostgreSQL provisionado por Alembic; triggers e constraints reais, sem `create_all()` |
| Unicidade | Confirmar que alteração de status preserva barcode e demais identificadores; manter regressão do barcode único. Não inventar conflito de unicidade próprio do status |
| Frontend | Payload correto, seleção, envio único, feedback, atualização após sucesso, estado preservado em falha e recarga após conflito |
| Migration, se houver | Upgrade/downgrade/upgrade em banco descartável e validação de compatibilidade dos dados |

### 6. Documentação, revisão e entrega

- Atualizar `backend/README.md` com contrato, papéis, exemplos e códigos de erro; atualizar regras e o escopo UX diretamente afetado.
- Rastrear PR e evidências à issue #31 / EAP 1.5.4, referenciando #28 e #21.
- Executar em ambiente de teste preparado: `pytest -q`, `alembic check`, `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`. Usar banco descartável para o ciclo de downgrade.
- Executar testes Angular sem watch e build; validar manualmente fluxo autorizado, erro e persistência após recarga.
- DoD só concluída com integração comprovada, revisão, aprovação e merge da PR. Este planejamento não satisfaz esses itens de implementação.

## Validação realizada e limites

- Suíte backend executada: **217 passed, 2 failed**, um aviso de depreciação.
- Falhas: `test_postgresql_aceita_obra_e_exemplar_e_rollback_nao_deixa_parcial` e `test_cadastro_de_funcionario_aceita_administrador`, ambas por conexão recusada em PostgreSQL local `127.0.0.1:54322`. Não representam defeito funcional confirmado.
- Ambiente virtual observado usa Python 3.14, divergindo do Python 3.12 declarado no AGENTS.md. Revalidar no runtime definido pelo projeto antes da entrega.
- Alembic check e ciclo de migrations não executados nesta análise: banco indisponível e tarefa limitada a diagnóstico/plano. Nenhuma migration foi alterada ou aplicada.
- Frontend inspecionado estaticamente; testes e build não executados nesta análise.
- A estimativa original de 3 SP / 4,5h só deve ser reutilizada após fechar o escopo. Edição manual, acesso a inativos e novas invariantes podem exigir reestimativa.
