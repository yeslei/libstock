import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';
import { AuthService } from '../../../core/services/auth.service';
import { CatalogService } from '../services/catalog.service';
import { CatalogBookDetail } from '../models/catalog.model';
import { ClientRequestsService, LoanRequestResponse } from '../../client-tracking/client-requests.service';
import { BookDetailsComponent } from './book-details.component';
import { todayInSaoPaulo } from './loan-dates';

describe('BookDetailsComponent', () => {
  let fixture: ComponentFixture<BookDetailsComponent>;
  let catalog: jasmine.SpyObj<CatalogService>;
  let requests: jasmine.SpyObj<ClientRequestsService>;
  let auth: any;
  const params = new BehaviorSubject(convertToParamMap({ id: '42' }));
  const detail: CatalogBookDetail = {
    id: 42, title: 'Dom Casmurro', author: 'Machado de Assis', isbn: '9788535914849',
    genres: ['Romance'], cover_url: null, offers: [],
    availability: {
      loan: { available: true, available_count: 2, configured: true, price: null },
      sale: { available: false, available_count: 0, configured: true, price: null },
      local_consultation: { available: null, available_count: null, configured: false, price: null },
    },
  };

  beforeEach(async () => {
    params.next(convertToParamMap({ id: '42' }));
    catalog = jasmine.createSpyObj('CatalogService', ['getBook']);
    requests = jasmine.createSpyObj('ClientRequestsService', ['requestLoan', 'requestPurchase', 'reservePurchase']);
    catalog.getBook.and.returnValue(of(detail));
    auth = { user$: new BehaviorSubject({ role_codes: ['USER'] }), currentUser: { id: 1 }, restoreSession: () => Promise.resolve() };
    await TestBed.configureTestingModule({ imports: [BookDetailsComponent], providers: [
      provideRouter([]), { provide: CatalogService, useValue: catalog }, { provide: ClientRequestsService, useValue: requests }, { provide: AuthService, useValue: auth },
      { provide: ActivatedRoute, useValue: { paramMap: params } },
    ] }).compileComponents();
    fixture = TestBed.createComponent(BookDetailsComponent);
    fixture.detectChanges();
  });

  function root(): HTMLElement { return fixture.nativeElement; }
  function setDate(value: string): void {
    const input = root().querySelector<HTMLInputElement>('#pickup-date')!;
    input.value = value; input.dispatchEvent(new Event('input')); fixture.detectChanges();
  }
  async function submit(): Promise<void> {
    root().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await Promise.resolve(); await Promise.resolve(); fixture.detectChanges();
  }

  it('abre detalhes e recebe disponibilidade por modalidade do backend', () => {
    expect(catalog.getBook).toHaveBeenCalledWith(42);
    expect(root().textContent).toContain('Dom Casmurro');
    expect(root().textContent).toContain('9788535914849');
    expect(root().textContent).toContain('2 exemplar(es) disponíveis');
    expect(root().textContent).toContain('Consulta local não configurada');
    expect(root().querySelector('details')!.open).toBeFalse();
  });

  it('calcula o prazo em campo somente leitura', () => {
    setDate('2028-01-31');
    const due = root().querySelector<HTMLInputElement>('#due-date')!;
    expect(due.value).toBe('2028-02-29');
    expect(due.readOnly).toBeTrue();
  });

  it('mostra snackbar apenas depois da confirmação persistida e impede envio duplo', async () => {
    const response = new Subject<LoanRequestResponse>();
    requests.requestLoan.and.returnValue(response);
    setDate(todayInSaoPaulo());
    await submit();
    expect(root().querySelector('.snackbar')).toBeNull();
    await submit();
    expect(requests.requestLoan).toHaveBeenCalledTimes(1);
    response.next({ id: 1, book_id: 42, pickup_date: todayInSaoPaulo(), due_date: '2026-11-03', status: 'PENDING', created_at: '' });
    fixture.detectChanges();
    expect(root().querySelector('.snackbar')!.textContent).toContain('Solicitação de empréstimo realizada com sucesso.');
    expect(root().querySelector<HTMLButtonElement>('button.primary')!.disabled).toBeTrue();
    fixture.destroy();
  });

  it('preserva a data e permite repetir após erro sem falso sucesso', async () => {
    requests.requestLoan.and.returnValue(throwError(() => ({ detail: 'Não há exemplar disponível.', status: 409 })));
    setDate(todayInSaoPaulo()); await submit();
    expect(root().textContent).toContain('Não há exemplar disponível.');
    expect(root().querySelector('.snackbar')).toBeNull();
    expect(root().querySelector<HTMLInputElement>('#pickup-date')!.value).toBe(todayInSaoPaulo());
    expect(root().querySelector<HTMLButtonElement>('button.primary')!.disabled).toBeFalse();
  });

  it('leva visitante ao login com retorno para o livro', async () => {
    auth.currentUser = null;
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    setDate(todayInSaoPaulo()); await submit();
    expect(navigate).toHaveBeenCalledWith(['/login'], { queryParams: { redirectTo: '/livros/42' } });
    expect(requests.requestLoan).not.toHaveBeenCalled();
  });

  it('não envia data passada', async () => {
    setDate('2000-01-01'); await submit();
    expect(requests.requestLoan).not.toHaveBeenCalled();
    expect(root().textContent).toContain('Informe uma data de retirada válida');
  });

  it('solicita compra com retirada e confirma somente após persistência', async () => {
    const data = { ...detail, availability: { ...detail.availability, sale: { ...detail.availability.sale, available: true, available_count: 1 } } };
    catalog.getBook.and.returnValue(of(data));
    fixture.destroy(); fixture = TestBed.createComponent(BookDetailsComponent); fixture.detectChanges();
    requests.requestPurchase.and.returnValue(of({ id: 2, book_id: 42, pickup_date: todayInSaoPaulo(), status: 'PENDING', created_at: '' }));
    const input = root().querySelector<HTMLInputElement>('#purchase-date')!;
    input.value = todayInSaoPaulo(); input.dispatchEvent(new Event('input')); fixture.detectChanges();
    root().querySelector('form.purchase-form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await Promise.resolve(); await Promise.resolve(); fixture.detectChanges();
    expect(requests.requestPurchase).toHaveBeenCalledWith(42, todayInSaoPaulo());
    expect(root().querySelector('.snackbar')!.textContent).toContain('Solicitação de compra realizada com sucesso.');
    fixture.destroy();
  });

  it('reserva compra indisponível e permite acompanhar a fila após a API confirmar', async () => {
    const data = { ...detail, availability: { ...detail.availability, sale: { ...detail.availability.sale, can_reserve: true } } };
    catalog.getBook.and.returnValue(of(data));
    fixture.destroy(); fixture = TestBed.createComponent(BookDetailsComponent); fixture.detectChanges();
    const response = new Subject<any>();
    requests.reservePurchase.and.returnValue(response);
    const button = [...root().querySelectorAll('button')].find(b => b.textContent?.includes('Reservar compra'))!;
    button.click(); await Promise.resolve(); await Promise.resolve(); fixture.detectChanges();
    expect(requests.reservePurchase).toHaveBeenCalledOnceWith(42);
    expect(root().querySelector('.snackbar')).toBeNull();
    response.next({ id: 1, book_id: 42, status: 'WAITING', queue_position: 2 });
    fixture.detectChanges();
    expect(root().textContent).toContain('Reserva de compra realizada com sucesso.');
    expect(root().querySelector('a[href="/minhas-reservas"]')).not.toBeNull();
    fixture.destroy();
  });

  it('does not apply a request response to another book after navigation', async () => {
    const response = new Subject<LoanRequestResponse>();
    requests.requestLoan.and.returnValue(response);
    setDate(todayInSaoPaulo()); await submit();
    catalog.getBook.and.returnValue(of({ ...detail, id: 43, title: 'Outro livro' }));
    params.next(convertToParamMap({ id: '43' })); fixture.detectChanges();
    response.next({ id: 1, book_id: 42, pickup_date: todayInSaoPaulo(), due_date: '', status: 'PENDING', created_at: '' });
    fixture.detectChanges();
    expect(root().textContent).toContain('Outro livro');
    expect(root().querySelector('.snackbar')).toBeNull();
    expect(root().querySelector<HTMLButtonElement>('button.primary')!.disabled).toBeFalse();
  });
});
