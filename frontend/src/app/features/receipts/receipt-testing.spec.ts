import { Provider } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { NEVER } from 'rxjs';

import { ReceiptService } from './receipt.service';

/** Substitui a consulta do comprovante: nunca responde, e registra quais comprovantes foram pedidos. */
export function receiptStub(): Provider {
  return { provide: ReceiptService, useValue: { get: jasmine.createSpy('get').and.returnValue(NEVER) } };
}

export function receiptGet(): jasmine.Spy {
  return (TestBed.inject(ReceiptService) as unknown as { get: jasmine.Spy }).get;
}
