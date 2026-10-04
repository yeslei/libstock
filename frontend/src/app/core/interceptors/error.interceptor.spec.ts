import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiError } from '../models/auth.model';
import { errorInterceptor } from './error.interceptor';

describe('errorInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([errorInterceptor])), provideHttpClientTesting()],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function fail(status: number, body: object): ApiError {
    let received: ApiError | undefined;
    client.delete('/x').subscribe({ error: (error) => (received = error) });
    http.expectOne('/x').flush(body, { status, statusText: 'erro' });
    return received!;
  }

  it('mapeia o código estável da exclusão de exemplar para mensagem de UI', () => {
    expect(fail(404, { detail: 'x', code: 'copy_not_found' }).detail).toBe('O exemplar não foi encontrado. Atualize a obra.');
    expect(fail(409, { detail: 'x', code: 'copy_not_available' }).detail).toContain('não está disponível');
    expect(fail(409, { detail: 'x', code: 'copy_not_for_loan' }).detail).toContain('didáticos');
    expect(fail(409, { detail: 'x', code: 'copy_has_history' }).detail).toContain('possui histórico');
    expect(fail(409, { detail: 'x', code: 'last_active_copy' }).detail).toContain('último exemplar ativo');
    expect(fail(500, { detail: 'x', code: 'copy_delete_persistence_error' }).detail).toContain('Nada foi alterado');
  });

  it('mapeia os códigos estáveis de reativação de obra e edição de exemplar', () => {
    expect(fail(409, { detail: 'x', code: 'book_without_active_copy' }).detail).toContain('sem ao menos um exemplar ativo');
    expect(fail(409, { detail: 'x', code: 'copy_inactive' }).detail).toContain('inativo');
    expect(fail(409, { detail: 'x', code: 'copy_allocated' }).detail).toContain('reserva de compra');
    expect(fail(409, { detail: 'x', code: 'copy_in_operation' }).detail).toContain('venda em andamento');
    expect(fail(409, { detail: 'x', code: 'copy_needed_for_requests' }).detail).toContain('solicitação de retirada pendente');
    expect(fail(422, { detail: 'x', code: 'copy_sale_price_required' }).detail).toContain('maior que zero');
    expect(fail(422, { detail: 'x', code: 'copy_sale_price_not_allowed' }).detail).toContain('didático');
    expect(fail(500, { detail: 'x', code: 'copy_update_persistence_error' }).detail).toContain('Nada foi alterado');
  });

  it('mapeia exemplar comercial sem preço na venda direta', () => {
    expect(fail(409, { detail: 'x', code: 'copy_without_price' }).detail).toBe(
      'Este exemplar comercial não tem preço de venda cadastrado e não pode ser vendido.',
    );
  });

  it('mapeia obra inativa em empréstimo e venda diretos', () => {
    expect(fail(409, { detail: 'x', code: 'book_inactive' }).detail).toBe('A obra deste exemplar está inativa e não aceita novas operações.');
  });

  it('mapeia a inativação bloqueada e preserva código, status e os dados estruturados', () => {
    const details = { counts: { open_loans: 1 }, links: [{ type: 'open_loan' }] };
    const error = fail(409, { detail: 'x', code: 'book_has_active_operations', details });
    expect(error.detail).toBe('Esta obra possui operações em andamento e não pode ser inativada.');
    expect(error.code).toBe('book_has_active_operations');
    expect(error.status).toBe(409);
    expect(error.details).toEqual(details);
  });

  it('não inventa details quando o corpo não os traz', () => {
    expect(fail(409, { detail: 'Já existe.', code: 'outro' }).details).toBeUndefined();
  });
});
