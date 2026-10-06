import { capabilitiesFor } from './catalog-capabilities';

describe('capabilitiesFor', () => {
  it('não oferece cadastro de exemplar na vitrine: ele passou para o balcão (Issue #169)', () => {
    for (const role of ['USER', 'SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'] as const) {
      expect([...capabilitiesFor([role])]).not.toContain('registerCopy' as never);
    }
  });

  it('mantém o destaque do catálogo para o administrador', () => {
    expect(capabilitiesFor(['ADMINISTRATOR']).has('manageCatalog')).toBeTrue();
    expect(capabilitiesFor(['STOCK_KEEPER']).has('manageCatalog')).toBeFalse();
  });
});
