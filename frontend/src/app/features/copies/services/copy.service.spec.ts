import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CopyCreateRequest } from '../models/copy.model';
import { COPIES_API, CopyService } from './copy.service';

describe('CopyService', () => {
  let service: CopyService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(CopyService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const payload: CopyCreateRequest = {
    bookId: 8, barcode: 'ABC-001', destination: 'COMMERCIAL', condition: 'Novo', salePrice: 19.9, acquiredAt: '2026-09-06',
  };

  it('envia POST com o contrato snake_case', () => {
    service.create(payload).subscribe();
    const request = http.expectOne(`${COPIES_API}/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      book_id: 8, barcode: 'ABC-001', destination: 'COMMERCIAL', condition: 'Novo', sale_price: 19.9, acquired_at: '2026-09-06',
    });
    request.flush({ id: 1, book_id: 8, barcode: 'ABC-001', destination: 'COMMERCIAL', condition: 'Novo', sale_price: 19.9, acquired_at: '2026-09-06', status: 'AVAILABLE', is_active: true });
  });

  it('converte a resposta snake_case para camelCase', () => {
    let result: unknown;
    service.create(payload).subscribe((copy) => (result = copy));
    http.expectOne(`${COPIES_API}/`).flush({
      id: 1, book_id: 8, barcode: 'ABC-001', destination: 'COMMERCIAL', condition: null, sale_price: null, acquired_at: null, status: 'AVAILABLE', is_active: true,
    });
    expect(result).toEqual({
      id: 1, bookId: 8, barcode: 'ABC-001', destination: 'COMMERCIAL', condition: null, salePrice: null, acquiredAt: null, status: 'AVAILABLE', isActive: true,
    });
  });

  it('propaga erros HTTP sem mascarar status ou código', () => {
    let error: { status: number; error: { code: string } } | undefined;
    service.create(payload).subscribe({ error: (received) => (error = received) });
    http.expectOne(`${COPIES_API}/`).flush({ code: 'duplicate_barcode' }, { status: 409, statusText: 'Conflict' });
    expect(error?.status).toBe(409);
    expect(error?.error.code).toBe('duplicate_barcode');
  });
});
