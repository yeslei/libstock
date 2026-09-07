/**
 * Os quatro perfis do SRS (seção 1.3), consolidados no banco pela migration
 * 20260905_0007. `ATTENDANT` foi fundido em `SELLER` e `MANAGER` em
 * `ADMINISTRATOR`: eram o mesmo ator com dois códigos, herdados de migrations
 * que semearam papéis sem conhecimento uma da outra.
 *
 * A promoção de papel é operação exclusiva do backend / painel administrativo:
 * o cadastro público sempre recebe `USER`, atribuído pelo próprio servidor.
 */
export type RoleCode =
  /** Cliente | Leitor */
  | 'USER'
  /** Atendente de Caixa | Vendedor */
  | 'SELLER'
  /** Estoquista | Bibliotecário */
  | 'STOCK_KEEPER'
  /** Gerente | Dono | Administrador */
  | 'ADMINISTRATOR';

export interface User {
  readonly id: number;
  readonly name: string;
  readonly email: string;
  /** Ex.: `['USER']` para um cadastro recém-criado. */
  readonly role_codes: RoleCode[];
  readonly created_at: string;
}
