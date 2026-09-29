import { capabilitiesFor } from './catalog-capabilities';

describe('capabilitiesFor', () => {
  it('inclui registerCopy somente para estoque e administração', () => {
    for (const role of ['STOCK_KEEPER', 'ADMINISTRATOR'] as const) {
      expect(capabilitiesFor([role]).has('registerCopy')).toBeTrue();
    }
    expect(capabilitiesFor(['SELLER']).has('registerCopy')).toBeFalse();
  });

  it('não inclui registerCopy para USER', () => expect(capabilitiesFor(['USER']).has('registerCopy')).toBeFalse());
});
