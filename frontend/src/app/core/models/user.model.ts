/**
 * Códigos de papel definidos no seed do backend
 * (migrations/versions/20260903_0003_add_user_roles.py).
 *
 * A promoção de papel é operação exclusiva do backend / painel administrativo:
 * o cadastro público sempre recebe `USER`, atribuído pelo próprio servidor.
 */
export type RoleCode =
  | 'USER'
  | 'SELLER'
  | 'MANAGER'
  | 'ATTENDANT'
  | 'STOCK_KEEPER'
  | 'ADMINISTRATOR';

export interface User {
  readonly id: number;
  readonly name: string;
  readonly email: string;
  /** Ex.: `['USER']` para um cadastro recém-criado. */
  readonly role_codes: RoleCode[];
  readonly created_at: string;
}
