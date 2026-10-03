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

    it('localiza exemplares por código, ISBN ou título', () => {
      service.lookupCopies(' 978-0 ').subscribe();
      const request = http.expectOne((r) => r.url === '/api/v1/staff/copies');
      expect(request.request.method).toBe('GET');
      expect(request.request.params.get('q')).toBe('978-0');
      expect(request.request.params.get('limit')).toBe('20');
      request.flush([]);
    });

    it('explica o termo ausente na busca de exemplares', () => {
      let error: ApiError | undefined;
      service.lookupCopies('x').subscribe({ error: (e) => (error = e) });
      http.expectOne(() => true).flush({ code: 'search_term_required', detail: 'x' }, { status: 422, statusText: 'x' });
      expect(error?.detail).toBe('Informe o código do exemplar, o ISBN ou o título.');
    });
  });

  describe('venda direta (endpoint anterior à V2)', () => {
    it('registra um exemplar ao preço cadastrado, sem cliente', () => {
      let result: unknown;
      service.registerSale(5, '38.90').subscribe((value) => (result = value));
      const request = http.expectOne('/api/v1/sales/');
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({ items: [{ copy_id: 5, unit_price: '38.90' }] });
      request.flush({ id: 12, total_amount: '38.90', status: 'PENDING' });
      expect(result).toEqual({ id: 12, total_amount: '38.90', status: 'PENDING' });
    });

    it('propaga conflito de disponibilidade com a mensagem do backend', () => {
      let error: ApiError | undefined;
      service.registerSale(5, '38.90').subscribe({ error: (e) => (error = e) });
      http.expectOne('/api/v1/sales/').flush({ detail: 'Um ou mais exemplares não estão disponíveis para venda.' }, { status: 409, statusText: 'x' });
      expect(error?.status).toBe(409);
      expect(error?.detail).toBe('Um ou mais exemplares não estão disponíveis para venda.');
    });

    it('propaga acesso negado sem tratar como sucesso', () => {
      let failed = false;
      service.registerSale(5, '38.90').subscribe({ error: () => (failed = true) });
      http.expectOne('/api/v1/sales/').flush({ detail: 'Permissão insuficiente.' }, { status: 403, statusText: 'x' });
      expect(failed).toBeTrue();
    });
  });
});
