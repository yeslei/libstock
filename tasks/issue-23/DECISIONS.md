# Decisions — Issue #23

## D-001 — Estratégia de correspondência

Status: APPROVED
Blocking: YES

A busca por título será parcial por substring.

Exemplo:

`cas`

pode encontrar títulos que contenham `cas`.

---

## D-002 — Case sensitivity

Status: APPROVED
Blocking: YES

A busca será case-insensitive.

Exemplo:

`dom`

deve encontrar:

`Dom Casmurro`

---

## D-003 — Obras inativas

Status: APPROVED
Blocking: YES

A busca padrão retorna apenas obras com:

`is_active = true`

---

## D-004 — Termo vazio

Status: APPROVED
Blocking: YES

Termo vazio ou composto somente por espaços é inválido.

O termo deve ser normalizado com trim antes da busca.

---

## D-005 — Paginação

Status: DEFERRED
Blocking: NO

Paginação não faz parte da primeira implementação da Issue #23.

Não criar infraestrutura genérica de paginação nesta Story.

---

## D-006 — Ordenação

Status: DEFERRED
Blocking: NO

Não adicionar regra de ordenação específica nesta Story, salvo se o padrão existente do projeto exigir.

---

## D-007 — Autenticação

Status: APPROVED
Blocking: YES

A Issue #23 não deve criar uma nova política de autorização.

A rota deve seguir o comportamento já adotado pelo projeto para consultas de catálogo/Explore.

Caso ainda não exista RBAC para esse domínio, não criar uma regra específica nesta Story.