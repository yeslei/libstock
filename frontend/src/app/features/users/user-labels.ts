import { RoleCode } from '../../core/models/user.model';

export interface RoleOption {
  readonly label: string;
  readonly value: RoleCode;
}

export const ROLE_OPTIONS: readonly RoleOption[] = [
  { label: 'Cliente', value: 'USER' },
  { label: 'Vendedor', value: 'SELLER' },
  { label: 'Estoquista', value: 'STOCK_KEEPER' },
  { label: 'Administrador', value: 'ADMINISTRATOR' },
];

export function roleLabel(role: string): string {
  return ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role;
}
