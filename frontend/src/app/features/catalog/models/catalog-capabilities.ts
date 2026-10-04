import { RoleCode } from '../../../core/models/user.model';

/**
 * O que cada papel faz na vitrine, derivado das histórias de usuário do SRS.
 *
 * Modelado como capacidade e não como papel para que a tela não precise
 * conhecer a lista de papéis: acrescentar um perfil novo é acrescentar uma
 * linha no mapa abaixo, sem tocar em template nenhum.
 */
export type CatalogCapability =
  /** US02 — cliente: comprar, pedir emprestado, reservar compra. */
  | 'transact'
  /** US01/US05 — atendente: registrar venda, empréstimo e devolução. */
  | 'counterService'
  /** US04 — gerente/administrador: destaque e conversão de destinação. */
  | 'manageCatalog';

const CAPABILITIES_BY_ROLE: Record<RoleCode, CatalogCapability[]> = {
  USER: ['transact'],
  SELLER: ['counterService'],
  // Cadastro de obra e exemplar acontece no balcão (Issue #169), não na vitrine.
  STOCK_KEEPER: [],
  // "Administrador com controle total das regras de negócio" (SRS, 1.3).
  ADMINISTRATOR: ['counterService', 'manageCatalog'],
};

export function capabilitiesFor(roleCodes: readonly RoleCode[]): Set<CatalogCapability> {
  const capabilities = new Set<CatalogCapability>();
  for (const role of roleCodes) {
    for (const capability of CAPABILITIES_BY_ROLE[role] ?? []) {
      capabilities.add(capability);
    }
  }
  return capabilities;
}
