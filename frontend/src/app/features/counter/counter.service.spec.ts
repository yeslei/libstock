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

  it('lê os indicadores do painel pelo endpoint somente leitura', () => {
    let result: unknown;
    service.getDashboard().subscribe((value) => (result = value));
    const request = http.expectOne('/api/v1/staff/dashboard');
    expect(request.request.method).toBe('GET');
    request.flush({ active_loans: 3, returns_today: 2, waiting_reservations: 1, pendencies: 4 });
    expect(result).toEqual({ active_loans: 3, returns_today: 2, waiting_reservations: 1, pendencies: 4 });
  });

  it('propaga o erro de domínio do painel (funcionário inativo)', () => {
    let error: ApiError | undefined;
    service.getDashboard().subscribe({ error: (e) => (error = e) });
    http.expectOne('/api/v1/staff/dashboard').flush(
      { code: 'employee_record_required', detail: 'Cadastro de funcionário ativo necessário.' },
      { status: 403, statusText: 'Forbidden' },
    );
    expect(error?.status).toBe(403);
  });

  it('lista clientes ativos sem enviar termo (lista padrão do balcão)', () => {
    service.searchClients().subscribe();
    const request = http.expectOne((r) => r.url === '/api/v1/staff/clients');
    expect(request.request.params.has('q')).toBeFalse();
    expect(request.request.params.get('limit')).toBe('20');
    request.flush([]);
  });

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

  it("cancela reserva com motivo opcional e efetiva a expiração por POST", () => {
    service.cancelReservation(6).subscribe();
    service.cancelReservation(7, "  Cliente desistiu  ").subscribe();
    service.expireDueReservations().subscribe();
    const plain = http.expectOne((r) => r.url === "/api/v1/staff/purchase-reservations/6/cancel");
    expect(plain.request.method).toBe("POST");
    expect(plain.request.body).toEqual({});
    plain.flush({ id: 6 });
    const withReason = http.expectOne("/api/v1/staff/purchase-reservations/7/cancel");
    expect(withReason.request.body).toEqual({ reason: "Cliente desistiu" });
    withReason.flush({ id: 7 });
    const expire = http.expectOne("/api/v1/staff/purchase-reservations/expire");
    expect(expire.request.method).toBe("POST");
    expire.flush({ expired: 0 });
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

  describe('acervo e exemplares (somente leitura)', () => {
    it('lista obras pelo termo, com limite explícito', () => {
      let result: unknown;
      service.listCatalogBooks('  dom ').subscribe((value) => (result = value));
      const request = http.expectOne((r) => r.url === '/api/v1/staff/books');
      expect(request.request.method).toBe('GET');
      expect(request.request.params.get('q')).toBe('dom');
      expect(request.request.params.get('limit')).toBe('50');
      request.flush([]);
      expect(result).toEqual([]);
    });

    it('lê o detalhe da obra com os exemplares', () => {
      let result: unknown;
      service.getCatalogBook(7).subscribe((value) => (result = value));
      const request = http.expectOne('/api/v1/staff/books/7');
      expect(request.request.method).toBe('GET');
      request.flush({ id: 7, copies: [] });
      expect(result).toEqual({ id: 7, copies: [] } as never);
    });

    it('propaga obra inexistente como erro de domínio', () => {
      let error: ApiError | undefined;
      service.getCatalogBook(99).subscribe({ error: (e) => (error = e) });
      http.expectOne('/api/v1/staff/books/99').flush({ code: 'book_not_found', detail: 'Obra não encontrada.' }, { status: 404, statusText: 'x' });
      expect(error?.status).toBe(404);
      expect(error?.code).toBe('book_not_found');
    });

    it('lista exemplares sem termo, filtrando por finalidade e disponibilidade', () => {
      service.listCopies({ destination: 'COMMERCIAL', available: true }).subscribe();
      const request = http.expectOne((r) => r.url === '/api/v1/staff/copies');
      expect(request.request.params.has('q')).toBeFalse();
      expect(request.request.params.get('destination')).toBe('COMMERCIAL');
      expect(request.request.params.get('available')).toBe('true');
      expect(request.request.params.get('limit')).toBe('20');
      request.flush([]);
    });

    it('a busca filtra dentro da lista de disponíveis: envia q junto com destination e available', () => {
      service.listCopies({ destination: 'DIDACTIC', available: true }, ' 978-0 ').subscribe();
      const request = http.expectOne((r) => r.url === '/api/v1/staff/copies');
      expect(request.request.params.get('q')).toBe('978-0');
      expect(request.request.params.get('destination')).toBe('DIDACTIC');
      expect(request.request.params.get('available')).toBe('true');
      expect(request.request.params.get('limit')).toBe('20');
      request.flush([]);
    });

    it('termo vazio ou só com espaços volta à lista padrão, sem q', () => {
      service.listCopies({ destination: 'COMMERCIAL', available: true }, '  ').subscribe();
      const request = http.expectOne((r) => r.url === '/api/v1/staff/copies');
      expect(request.request.params.has('q')).toBeFalse();
      request.flush([]);
    });
  });

  describe('venda direta', () => {
    it('registra a venda em POST /api/v1/sales/ com o cliente e sem enviar preço', () => {
      let result: unknown;
      service.registerSale(3, 7).subscribe((value) => (result = value));
      const request = http.expectOne('/api/v1/sales/');
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({ client_id: 3, items: [{ copy_id: 7 }] });
      request.flush({ id: 5, client_id: 3, status: 'CONFIRMED', total_amount: '38.90' }, { status: 201, statusText: 'Created' });
      expect(result).toEqual(jasmine.objectContaining({ id: 5, status: 'CONFIRMED' }));
    });

    it('propaga o erro de exemplar sem preço cadastrado', () => {
      let error: ApiError | undefined;
      service.registerSale(3, 7).subscribe({ error: (e) => (error = e) });
      http.expectOne('/api/v1/sales/').flush({ detail: 'x', code: 'copy_without_price' }, { status: 409, statusText: 'Conflict' });
      expect(error?.code).toBe('copy_without_price');
    });

    it('propaga o erro de domínio do exemplar didático', () => {
      let error: ApiError | undefined;
      service.registerSale(3, 7).subscribe({ error: (e) => (error = e) });
      http.expectOne('/api/v1/sales/').flush({ detail: 'Exemplares didáticos não podem ser vendidos.' }, { status: 409, statusText: 'Conflict' });
      expect(error?.status).toBe(409);
      expect(error?.detail).toBe('Exemplares didáticos não podem ser vendidos.');
    });
  });

  describe('empréstimo direto', () => {
    it('registra em POST /api/v1/loans/ apenas com cliente e exemplar, sem prazo', () => {
      let result: unknown;
      service.registerLoan(3, 9).subscribe((value) => (result = value));
      const request = http.expectOne('/api/v1/loans/');
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({ client_id: 3, copy_id: 9 });
      const created = { id: 1, client_id: 3, copy_id: 9, employee_id: 2, loan_date: '2026-10-03T12:00:00Z', due_date: '2026-10-18T12:00:00Z', returned_at: null, status: 'OPEN' };
      request.flush(created, { status: 201, statusText: 'Created' });
      expect(result).toEqual(created);
    });

    it('propaga o código e a mensagem do erro de domínio do cliente', () => {
      let error: ApiError | undefined;
      service.registerLoan(3, 9).subscribe({ error: (e) => (error = e) });
      http.expectOne('/api/v1/loans/').flush(
        { detail: 'Cliente possui pendência ativa e não pode realizar a operação.', code: 'client_has_pending' },
        { status: 409, statusText: 'Conflict' },
      );
      expect(error?.status).toBe(409);
      expect(error?.code).toBe('client_has_pending');
    });

    it('propaga o conflito de exemplar indisponível', () => {
      let error: ApiError | undefined;
      service.registerLoan(3, 9).subscribe({ error: (e) => (error = e) });
      http.expectOne('/api/v1/loans/').flush({ detail: 'Exemplar não está disponível para empréstimo.' }, { status: 409, statusText: 'Conflict' });
      expect(error?.status).toBe(409);
      expect(error?.detail).toBe('Exemplar não está disponível para empréstimo.');
    });
  });
});
