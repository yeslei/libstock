import { capabilitiesFor } from './catalog-capabilities';

describe('capabilitiesFor', () => {
  it('inclui registerCopy para os três papéis operacionais', () => {
    for (const role of ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'] as const) {
      expect(capabilitiesFor([role]).has('registerCopy')).toBeTrue();
    }
  });

  it('não inclui registerCopy para USER', () => expect(capabilitiesFor(['USER']).has('registerCopy')).toBeFalse());
});
