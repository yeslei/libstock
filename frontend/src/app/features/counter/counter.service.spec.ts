import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiError } from '../../core/models/auth.model';
import { errorInterceptor } from '../../core/interceptors/error.interceptor';
import { CounterService } from './counter.service';

describe('CounterService', () => {
  let service: CounterService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([errorInterceptor])), provideHttpClientTesting()],
    });
    service = TestBed.inject(CounterService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('busca clientes por termo aparado no endpoint de balcão', () => {
    service.searchClients('  ana  ').subscribe();
    const request = http.expectOne((r) => r.url === '/api/v1/staff/clients');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('q')).toBe('ana');
    expect(request.request.params.get('limit')).toBe('20');
    request.flush([]);
  });

  it('consulta pendências pelo endpoint de balcão somente leitura, não pelo V1', () => {
    service.getClientPendencies(7).subscribe();
    const request = http.expectOne('/api/v1/staff/clients/7/pendencies');
    expect(request.request.method).toBe('GET');
    request.flush({});
  });

  it('lista solicitações, empréstimos e reservas enviando só filtros informados', () => {
    service.listLoanRequests().subscribe();
    service.listLoans({ q: ' dom ', clientId: 5 }).subscribe();
    service.listPurchaseReservations({ q: '', clientId: null, status: 'WAITING' }).subscribe();
    const requests = http.expectOne((r) => r.url === '/api/v1/staff/loan-requests');
    expect(requests.request.params.keys()).toEqual(['limit']);
    expect(requests.request.params.get('limit')).toBe('50');
    const loans = http.expectOne((r) => r.url === '/api/v1/staff/loans');
    expect(loans.request.params.get('q')).toBe('dom');
    expect(loans.request.params.get('client_id')).toBe('5');
    const reservations = http.expectOne((r) => r.url === '/api/v1/staff/purchase-reservations');
    expect(reservations.request.params.keys()).toEqual(['status', 'limit']);
    expect(reservations.request.params.get('status')).toBe('WAITING');
    [requests, loans, reservations].forEach((r) => {
      expect(r.request.method).toBe('GET');
      r.flush([]);
    });
  });

  it('confirma retirada enviando apenas o exemplar escolhido', () => {
    service.confirmPickup(11, 99).subscribe((result) => expect(result.id).toBe(3));
    const request = http.expectOne('/api/v1/staff/loan-requests/11/confirm-pickup');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ copy_id: 99 });
    request.flush({ id: 3 });
  });

  it('usa POST V2 para devolução, destinação e venda', () => {
    service.confirmReturn(4).subscribe();
    service.allocatePurchase(8).subscribe();
    service.confirmSale(6).subscribe();
    for (const url of [
      '/api/v1/staff/loans/4/confirm-return',
      '/api/v1/staff/books/8/allocate-purchase',
      '/api/v1/staff/purchase-reservations/6/confirm-sale',
    ]) {
      const request = http.expectOne(url);
      expect(request.request.method).toBe('POST');
      request.flush({ id: 1 });
    }
  });

  it('nunca usa os endpoints transacionais antigos', () => {
    service.confirmReturn(1).subscribe();
    const request = http.expectOne(() => true);
    expect(request.request.url).not.toMatch(/^\/api\/v1\/(loans|sales)/);
    request.flush({ id: 1 });
  });

  it('traduz códigos de domínio V2 em mensagens compreensíveis', () => {
    const cases: [string, number, string][] = [
      ['pickup_already_confirmed', 409, 'A retirada desta solicitação já foi confirmada.'],
      ['client_ineligible', 403, 'O cliente está inativo, penalizado ou com empréstimo em atraso.'],
      ['loan_already_closed', 409, 'Este empréstimo já foi encerrado.'],
      ['purchase_unavailable', 409, 'Não há exemplar comercial livre para esta operação.'],
      ['reservation_expired', 409, 'O prazo de retirada desta reserva expirou.'],
    ];
    for (const [code, status, message] of cases) {
      let error: ApiError | undefined;
      service.confirmReturn(1).subscribe({ error: (e) => (error = e) });
      http.expectOne(() => true).flush({ detail: 'texto do backend', code }, { status, statusText: 'x' });
      expect(error?.detail).toBe(message);
      expect(error?.code).toBe(code);
    }
  });
});
