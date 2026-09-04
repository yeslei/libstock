<!-- libstock-eap-task: EAP-1.5.6 -->

## História de usuário

Como **atendente**,
quero **registrar uma devolução**,
para **encerrar corretamente o empréstimo e atualizar a disponibilidade do exemplar**.

## Contexto

Esta história deriva da issue #33 e do planejamento original do projeto LibStock.

O objetivo é transformar o pacote de trabalho original em uma entrega funcional verificável, mantendo a rastreabilidade com a EAP.

## Critérios de aceitação

- [ ] O fluxo principal deve estar disponível para o usuário autorizado.
- [ ] Os dados obrigatórios devem ser validados.
- [ ] Dados inválidos devem produzir resposta de erro adequada.
- [ ] A operação não deve deixar dados inconsistentes.
- [ ] O resultado da operação deve poder ser validado pelo usuário.

## Regras de negócio

- RN01 — A operação deve respeitar as regras existentes do domínio LibStock.
- RN02 — Operações protegidas devem exigir usuário autenticado quando aplicável.
- RN03 — Alterações persistentes devem manter consistência dos dados.

## Dependências

- Dependências EAP: `1.5.3, 1.5.4`

## Escopo técnico esperado

### Backend

- [ ] Definir ou atualizar schemas.
- [ ] Implementar camada de serviço.
- [ ] Implementar ou atualizar repository.
- [ ] Disponibilizar endpoint quando aplicável.
- [ ] Implementar validações.
- [ ] Implementar testes automatizados.

### Frontend

- [ ] Implementar interface quando aplicável.
- [ ] Integrar com a API.
- [ ] Validar entradas do usuário.
- [ ] Exibir feedback de sucesso e erro.

## Fora do escopo

- Funcionalidades não previstas nesta história.
- Alterações em outros módulos sem dependência direta.

## Definition of Done

- [ ] Critérios de aceitação atendidos.
- [ ] Código revisado.
- [ ] Testes automatizados passando.
- [ ] Integração validada.
- [ ] Documentação atualizada quando necessário.
- [ ] PR aprovada e integrada.

## Rastreabilidade

- Issue original: #33
- Milestone planejado: V2
- Prioridade planejada: P1
- Tamanho planejado: S

<details>
<summary>Dados originais da EAP</summary>

| Campo | Valor |
| --- | --- |
| ID EAP | 1.5.6 |
| Pacote principal | Gestão de Empréstimos e Devoluções |
| SP final | 3 |
| Dependencias | 1.5.3, 1.5.4 |
| Responsavel | Danilo |
| Apoio | Sandy |
| Horas previstas | 4,5h |
| Duracao em dias uteis | 1 |
| Valor/hora | R$ 30,00 |
| Custo previsto | R$ 135,00 |
| Status planejado | Backlog |
| Observacoes | Subpacote oficial da EAP enviada pela equipe. |

</details>
