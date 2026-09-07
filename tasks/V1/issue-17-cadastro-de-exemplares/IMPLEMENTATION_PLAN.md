# Plano de Implementacao Frontend - Issue #17: Cadastro de Exemplares

## 1. Escopo

- Issue: `#17 - [US] Cadastro de exemplares`
- Branch: `feature/cadastro-exemplares`
- Backend existente: `POST /api/v1/copies/`
- Nesta execucao: planejar somente o frontend.
- Fora de escopo nesta execucao: implementar frontend, alterar backend, migrations, dependencias, `README.md`, `AGENTS.md`, commit ou push.

## 2. Contrato Confirmado

### Endpoint

- Metodo: `POST`
- URL backend: `/api/v1/copies/`
- Sucesso: `201 Created`
- Controller: `backend/app/controllers/copy_controller.py`
- Service de dominio: `backend/app/services/copy_service.py`
- Schemas backend: `backend/app/schemas/copy_schema.py`

### Request planejado no frontend

Criar `CopyCreateRequest` em `frontend/src/app/features/copies/models/copy.model.ts`:

```ts
export type DestinationType = 'COMMERCIAL' | 'DIDACTIC';

export interface CopyCreateRequest {
  readonly bookId: number;
  readonly barcode: string;
  readonly destination: DestinationType;
  readonly condition: string | null;
  readonly salePrice: number | null;
  readonly acquiredAt: string | null;
}
```

O `CopyService` deve converter para o contrato snake_case do backend:

```ts
{
  book_id: payload.bookId,
  barcode: payload.barcode,
  destination: payload.destination,
  condition: payload.condition,
  sale_price: payload.salePrice,
  acquired_at: payload.acquiredAt,
}
```

### Response planejado no frontend

Criar `CopyResponse` em `frontend/src/app/features/copies/models/copy.model.ts`:

```ts
export type CopyStatus = 'AVAILABLE' | 'BORROWED' | 'SOLD' | 'RESERVED' | 'INACTIVE';

export interface CopyResponse {
  readonly id: number;
  readonly bookId: number;
  readonly barcode: string;
  readonly destination: DestinationType;
  readonly condition: string | null;
  readonly salePrice: number | null;
  readonly acquiredAt: string | null;
  readonly status: CopyStatus;
  readonly isActive: boolean;
}
```

`salePrice` fica modelado como `number | null`. Esta confirmacao deriva do contrato Pydantic/encoder observado para `Decimal` e nao de um `TestClient` HTTP completo da rota autenticada.

## 3. Rota

- Rota de UI: `/obras/:id/exemplares/novo`
- Arquivo: `frontend/src/app/app.routes.ts`
- Guards: `authGuard` e `roleGuard('SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR')`
- Lazy load: `CopyCreateComponent`
- Parametro `:id`: validar no componente como inteiro positivo finito; rota invalida deve exibir erro de parametro e impedir submit.

Exemplo planejado:

```ts
{
  path: 'obras/:id/exemplares/novo',
  canActivate: [authGuard, roleGuard('SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR')],
  title: 'Cadastrar exemplar · LibStock',
  loadComponent: () =>
    import('./features/copies/copy-create/copy-create.component').then(
      (m) => m.CopyCreateComponent,
    ),
}
```

## 4. Roles e Capacidade Planejada

Roles efetivas no frontend:

- `SELLER`
- `STOCK_KEEPER`
- `ADMINISTRATOR`

Nao adicionar `MANAGER` novamente ao `RoleCode`; a migration `20260905_0007_consolidate_roles.py` consolida `MANAGER` em `ADMINISTRATOR` e `ATTENDANT` em `SELLER`. O `MANAGER` que ainda aparece no controller de copy e compatibilidade legada do backend.

Reavaliacao de autorizacao:

- `SELLER` possui `counterService`.
- `STOCK_KEEPER` possui `manageStock`.
- `ADMINISTRATOR` possui `counterService` e `manageStock`.
- O backend permite que `SELLER` cadastre exemplar.

Portanto, nao usar `manageStock` isoladamente para cadastro de exemplar, pois isso esconderia de `SELLER` uma operacao permitida pelo backend.

Planejar capacidade especifica em `frontend/src/app/features/catalog/models/catalog-capabilities.ts`:

```ts
export type CatalogCapability =
  | 'transact'
  | 'counterService'
  | 'manageStock'
  | 'manageCatalog'
  | 'registerCopy';
```

Mapa planejado:

- `USER`: `['transact']`
- `SELLER`: `['counterService', 'registerCopy']`
- `STOCK_KEEPER`: `['manageStock', 'registerCopy']`
- `ADMINISTRATOR`: `['counterService', 'manageStock', 'manageCatalog', 'registerCopy']`

O backend permanece a autoridade final via `require_roles`.

## 5. Ponto de Entrada

- Arquivo: `frontend/src/app/features/catalog/catalog-home/catalog-home.component.ts`
- Arquivo: `frontend/src/app/features/catalog/catalog-home/catalog-home.component.html`
- Entrada: acao visivel no card da obra em `CatalogHomeComponent`, usando `book.id`.
- Condicao de exibicao: `canRegisterCopy()` derivado da capacidade `registerCopy`.
- Navegacao: `[routerLink]="['/obras', book.id, 'exemplares', 'novo']"`
- Nao modificar `HomeComponent`.
- A acao deve ser separada da acao transacional principal do card para nao depender de disponibilidade de oferta.

## 6. Arquivos Previstos

- `frontend/src/app/app.routes.ts`
- `frontend/src/app/core/guards/role.guard.ts` somente reutilizacao, sem alteracao prevista
- `frontend/src/app/features/catalog/models/catalog-capabilities.ts`
- `frontend/src/app/features/catalog/catalog-home/catalog-home.component.ts`
- `frontend/src/app/features/catalog/catalog-home/catalog-home.component.html`
- `frontend/src/app/features/copies/models/copy.model.ts`
- `frontend/src/app/features/copies/services/copy.service.ts`
- `frontend/src/app/features/copies/services/copy.service.spec.ts`
- `frontend/src/app/features/copies/copy-create/copy-create.component.ts`
- `frontend/src/app/features/copies/copy-create/copy-create.component.html`
- `frontend/src/app/features/copies/copy-create/copy-create.component.scss`
- `frontend/src/app/features/copies/copy-create/copy-create.component.spec.ts`

## 7. Componente Standalone

Criar `CopyCreateComponent` standalone com:

- `ReactiveFormsModule`
- `RouterLink`
- `ActivatedRoute`
- `CopyService`
- `DestroyRef`
- `AlertComponent`
- `SpinnerComponent`

Estados previstos:

- `idle`
- `submitting`
- `success`
- `error`
- `invalidRoute`

Comportamento:

- Permanecer na tela apos sucesso.
- Exibir os dados reais retornados em `CopyResponse`.
- Oferecer botao `Cadastrar outro exemplar`.
- Ao cadastrar outro exemplar, resetar campos editaveis e manter o `bookId` da rota.
- Preservar formulario depois de erro.
- Impedir envio duplo enquanto `submitting`.

## 8. Formulario Reativo

Campos:

- `barcode`: obrigatorio, trim antes do envio, maximo 100 caracteres.
- `destination`: obrigatorio com escolha explicita entre `COMMERCIAL` e `DIDACTIC`.
- `condition`: opcional, trim antes do envio, maximo 30 caracteres.
- `salePrice`: obrigatorio somente quando `destination === 'COMMERCIAL'`.
- `acquiredAt`: opcional.

Normalizacao antes do submit:

- `barcode`: `value.trim()`
- `condition`: `value.trim() || null`
- `acquiredAt`: `value || null`
- `salePrice`: `number` para `COMMERCIAL`; `null` para `DIDACTIC`
- opcionais vazios enviados como `null`

Validacao monetaria:

- obrigatorio somente para `COMMERCIAL`
- valor nao negativo
- maximo de 10 digitos no total
- no maximo duas casas decimais
- para `DIDACTIC`, nao enviar preco; enviar `salePrice: null`

## 9. CopyService

Criar `frontend/src/app/features/copies/services/copy.service.ts` com:

- metodo publico `create(payload: CopyCreateRequest): Observable<CopyResponse>`
- `POST` para `/api/v1/copies/`
- mapeamento request camelCase -> snake_case
- mapeamento response snake_case -> camelCase
- sem regras de dominio alem da adaptacao de contrato HTTP

## 10. Tratamento de Erros

Usar o contrato normalizado por `frontend/src/app/core/interceptors/error.interceptor.ts`.

Planejar tratamento no componente:

- `401`: exibir mensagem de sessao expirada/nao autenticada recebida do interceptor.
- `403`: exibir permissao negada.
- `404`: obra inexistente ou inativa; manter formulario.
- `409`: barcode duplicado; manter formulario e focar `barcode`.
- `422`: associar validacoes a campos quando o backend informar `loc`; manter formulario.
- `500` ou status inesperado: alerta generico vindo do interceptor; manter formulario.

## 11. Testes Unitarios Planejados

Quantidade total: 24 testes unitarios, separados por comportamento.

### `copy.service.spec.ts` - 3 testes

1. envia `POST /api/v1/copies/` com payload snake_case.
2. converte `CopyResponse` snake_case para camelCase, incluindo `sale_price` como `number | null`.
3. propaga erro HTTP ja normalizado pelo interceptor sem mascarar status/codigo.

### `copy-create.component.spec.ts` - 18 testes

1. cria o componente com rota valida.
2. marca rota invalida para `:id` ausente, nao numerico, zero ou negativo e bloqueia submit.
3. exige `barcode`.
4. aplica maximo de 100 caracteres em `barcode`.
5. trima `barcode` antes do envio.
6. exige escolha explicita de `destination`.
7. aplica maximo de 30 caracteres em `condition`.
8. converte `condition` vazia em `null`.
9. converte `acquiredAt` vazio em `null`.
10. exige `salePrice` somente para `COMMERCIAL`.
11. rejeita `salePrice` com mais de duas casas decimais.
12. rejeita `salePrice` acima de 10 digitos totais.
13. envia `salePrice: null` quando `DIDACTIC`.
14. bloqueia submit quando formulario invalido.
15. impede multiplos envios durante loading.
16. exibe dados reais de `CopyResponse` apos `201` e permanece na tela.
17. executa `Cadastrar outro exemplar`, limpando campos editaveis e mantendo `bookId`.
18. preserva formulario e trata erros `401`, `403`, `404`, `409`, `422` e `500` em casos parametrizados por status.

### Capacidades, rota e entrada - 3 testes

1. `capabilitiesFor` inclui `registerCopy` para `SELLER`, `STOCK_KEEPER` e `ADMINISTRATOR`.
2. `capabilitiesFor` nao inclui `registerCopy` para `USER`.
3. `CatalogHomeComponent` exibe link de cadastro de exemplar no card usando `book.id` quando `canRegisterCopy()` for verdadeiro.

## 12. Bloqueios

- Nenhum bloqueio para planejar a implementacao.
- Limite registrado: a confirmacao de `sale_price` como `number | null` vem do contrato/encoder do backend, nao de um `TestClient` HTTP completo da rota autenticada.
