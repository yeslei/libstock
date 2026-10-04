import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';
import { AuthService } from '../../../core/services/auth.service';
import { CatalogService } from '../services/catalog.service';
import { CatalogBookDetail } from '../models/catalog.model';
import { ClientTrackingService } from '../../client-tracking/client-tracking.service';
import { ClientRequestsService, LoanRequestResponse } from '../../client-tracking/client-requests.service';
import { BookDetailsComponent } from './book-details.component';
import { pickupDeadline, todayInSaoPaulo } from './loan-dates';

describe('BookDetailsComponent', () => {
  let fixture: ComponentFixture<BookDetailsComponent>;
  let catalog: jasmine.SpyObj<CatalogService>;
  let requests: jasmine.SpyObj<ClientRequestsService>;
  let tracking: jasmine.SpyObj<ClientTrackingService>;
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
    tracking = jasmine.createSpyObj('ClientTrackingService', ['getLoans', 'getEligibility']);
    tracking.getEligibility.and.returnValue(of({ eligible: true, reasons: [] }));
    tracking.getLoans.and.returnValue(of([]));
    catalog.getBook.and.returnValue(of(detail));
    auth = { user$: new BehaviorSubject({ name: 'Maria Silva', email: 'maria@email.com', role_codes: ['USER'] }), currentUser: { id: 1 }, restoreSession: () => Promise.resolve() };
    await TestBed.configureTestingModule({ imports: [BookDetailsComponent], providers: [
      provideRouter([]), { provide: CatalogService, useValue: catalog }, { provide: ClientRequestsService, useValue: requests }, { provide: ClientTrackingService, useValue: tracking }, { provide: AuthService, useValue: auth },
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
    expect(root().textContent).toContain('2 exemplares disponíveis');
    expect(root().textContent).toContain('Consulta local não configurada');
    expect(root().querySelector('details')!.open).toBeTrue();
    expect(root().querySelectorAll('details')[1].open).toBeFalse();
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

  it('limita a data de retirada da compra ao prazo e recusa data posterior sem chamar o backend', async () => {
    const data = { ...detail, availability: { ...detail.availability, sale: { ...detail.availability.sale, available: true, available_count: 1 } } };
    catalog.getBook.and.returnValue(of(data));
    fixture.destroy(); fixture = TestBed.createComponent(BookDetailsComponent); fixture.detectChanges();
    const input = root().querySelector<HTMLInputElement>('#purchase-date')!;
    expect(input.max).toBe(pickupDeadline());
    input.value = '9998-01-01'; input.dispatchEvent(new Event('input')); fixture.detectChanges();
    root().querySelector('form.purchase-form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await Promise.resolve(); await Promise.resolve(); fixture.detectChanges();
    expect(requests.requestPurchase).not.toHaveBeenCalled();
    expect(root().textContent).toContain('A data de retirada não pode passar de');
    fixture.destroy();
  });

  it('informa que a solicitação entrou no fim da fila quando a reserva nasce aguardando', async () => {
    const data = { ...detail, availability: { ...detail.availability, sale: { ...detail.availability.sale, available: true, available_count: 1 } } };
    catalog.getBook.and.returnValue(of(data));
    fixture.destroy(); fixture = TestBed.createComponent(BookDetailsComponent); fixture.detectChanges();
    requests.requestPurchase.and.returnValue(of({ id: 2, book_id: 42, pickup_date: todayInSaoPaulo(), status: 'PENDING', created_at: '', reservation_status: 'WAITING' }));
    const input = root().querySelector<HTMLInputElement>('#purchase-date')!;
    input.value = todayInSaoPaulo(); input.dispatchEvent(new Event('input')); fixture.detectChanges();
    root().querySelector('form.purchase-form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await Promise.resolve(); await Promise.resolve(); fixture.detectChanges();
    expect(root().querySelector('.snackbar')!.textContent).toContain('fim da fila de compra');
    fixture.destroy();
  });

  const reservable = { ...detail, availability: { ...detail.availability, sale: { ...detail.availability.sale, can_reserve: true } } };
  function rerender(data: CatalogBookDetail): void {
    catalog.getBook.and.returnValue(of(data));
    fixture.destroy(); fixture = TestBed.createComponent(BookDetailsComponent); fixture.detectChanges();
  }
  function button(label: string): HTMLButtonElement {
    return [...root().querySelectorAll('button')].find(b => b.textContent?.includes(label)) as HTMLButtonElement;
  }
  async function click(label: string): Promise<void> {
    button(label).click(); await Promise.resolve(); await Promise.resolve(); fixture.detectChanges();
  }
  const domainBlock = { detail: 'Cliente inativo, penalizado ou com empréstimo em atraso.', code: 'client_ineligible', status: 403 };

  it('mostra venda esgotada com a opção de entrar na fila e abre a venda por padrão', () => {
    rerender({ ...reservable, availability: { ...reservable.availability, loan: { ...detail.availability.loan, available: false, available_count: 0 } } });
    expect(root().textContent).toContain('Esgotado');
    expect(root().textContent).toContain('Você pode entrar na fila de compra');
    expect(root().textContent).toContain('A reserva não conclui uma compra.');
    expect(root().querySelectorAll('details')[1].open).toBeTrue();
    expect(button('Reservar compra')).toBeTruthy();
  });

  it('não oferece a fila quando o backend não permite reservar', () => {
    expect(root().textContent).not.toContain('Você pode entrar na fila de compra');
    expect(button('Reservar compra')).toBeUndefined();
  });

  it('pede confirmação antes de reservar e só cria depois de confirmar', async () => {
    rerender(reservable);
    await click('Reservar compra');
    expect(requests.reservePurchase).not.toHaveBeenCalled();
    expect(root().textContent).toContain('Confirmar reserva de compra');
    expect(root().textContent).toContain('Livro: Dom Casmurro');
    expect(root().textContent).toContain('Cliente: Maria Silva · maria@email.com');
    expect(root().textContent).toContain('Sua posição será informada após o registro.');
    await click('Voltar');
    expect(requests.reservePurchase).not.toHaveBeenCalled();
    expect(root().textContent).toContain('Disponibilidade');
  });

  it('mostra "Situação do cliente: apto" na confirmação da reserva', async () => {
    rerender(reservable);
    await click('Reservar compra');
    expect(tracking.getEligibility).toHaveBeenCalledTimes(1);
    expect(root().textContent).toContain('Situação do cliente: apto — conta ativa e sem pendências');
    expect(button('Confirmar reserva').disabled).toBeFalse();
  });

  it('mostra os motivos e bloqueia a confirmação quando o cliente está inapto', async () => {
    rerender(reservable);
    tracking.getEligibility.and.returnValue(of({ eligible: false, reasons: [
      { code: 'penalized', message: 'Cliente com penalidade ativa.' }, { code: 'overdue_loan', message: 'Há empréstimo em atraso.' },
    ] }));
    await click('Reservar compra');
    expect(root().textContent).toContain('Situação do cliente: inapto');
    expect(root().textContent).toContain('Cliente com penalidade ativa.');
    expect(root().textContent).toContain('Há empréstimo em atraso.');
    expect(root().querySelector('[role="alert"].situation--blocked')).not.toBeNull();
    expect(button('Confirmar reserva').disabled).toBeTrue();
    expect(requests.reservePurchase).not.toHaveBeenCalled();
  });

  it('mostra a verificação em andamento e a falha da consulta sem impedir o envio', async () => {
    rerender(reservable);
    const pending = new Subject<any>();
    tracking.getEligibility.and.returnValue(pending);
    await click('Reservar compra');
    expect(root().textContent).toContain('Verificando situação do cliente');
    pending.error({ status: 500 });
    fixture.detectChanges();
    expect(root().textContent).toContain('Não foi possível verificar a situação do cliente agora.');
    expect(button('Confirmar reserva').disabled).toBeFalse();
  });

  it('o bloqueio por pendência lista os motivos da elegibilidade, inclusive penalidade sem atraso', async () => {
    rerender(reservable);
    requests.reservePurchase.and.returnValue(throwError(() => domainBlock));
    // a confirmação vê o cliente apto; ao enviar, o backend recusa e a nova consulta traz o motivo
    tracking.getEligibility.and.returnValues(of({ eligible: true, reasons: [] }), of({ eligible: false, reasons: [{ code: 'penalized', message: 'Cliente com penalidade ativa.' }] }));
    await click('Reservar compra'); await click('Confirmar reserva');
    expect(root().textContent).toContain('Reserva bloqueada por pendência');
    expect(root().textContent).toContain('Cliente com penalidade ativa.');
  });

  it('registra a reserva só após a API, bloqueia duplo envio e mostra a posição retornada', async () => {
    rerender(reservable);
    const response = new Subject<any>();
    requests.reservePurchase.and.returnValue(response);
    await click('Reservar compra');
    const confirm = button('Confirmar reserva'); confirm.click(); confirm.click(); fixture.detectChanges();
    expect(requests.reservePurchase).toHaveBeenCalledOnceWith(42);
    expect(root().querySelector('.snackbar')).toBeNull();
    expect(root().textContent).not.toContain('Reserva registrada');
    response.next({ id: 1, book_id: 42, status: 'WAITING', queue_position: 2 });
    fixture.detectChanges();
    expect(root().textContent).toContain('Reserva registrada');
    expect(root().textContent).toContain('Você está em 2º lugar na fila de Dom Casmurro.');
    expect(root().textContent).toContain('A reserva não registra uma venda nem reduz o estoque.');
    expect(root().querySelector('.snackbar')!.textContent).toContain('Reserva de compra realizada com sucesso.');
    expect(root().querySelector('a[href="/minhas-reservas"]')).not.toBeNull();
    await click('Voltar ao livro');
    expect(button('Reserva enviada')!.disabled).toBeTrue();
    fixture.destroy();
  });

  it('erro de domínio na reserva não vira sucesso e permite repetir', async () => {
    rerender(reservable);
    requests.reservePurchase.and.returnValue(throwError(() => ({ detail: 'Há exemplar disponível. Solicite a compra com data de retirada.', code: 'purchase_available', status: 409 })));
    await click('Reservar compra'); await click('Confirmar reserva');
    expect(root().textContent).toContain('Há exemplar disponível.');
    expect(root().textContent).not.toContain('Reserva registrada');
    expect(root().querySelector('.snackbar')).toBeNull();
    expect(button('Reservar compra').disabled).toBeFalse();
  });

  it('reserva duplicada orienta a acompanhar em Minhas reservas', async () => {
    rerender(reservable);
    requests.reservePurchase.and.returnValue(throwError(() => ({ detail: 'Você já possui uma reserva de compra em andamento.', code: 'reservation_duplicate', status: 409 })));
    await click('Reservar compra'); await click('Confirmar reserva');
    expect(root().textContent).toContain('Você já possui uma reserva de compra em andamento.');
    expect(root().querySelector('a[href="/minhas-reservas"]')).not.toBeNull();
  });

  it('bloqueia a reserva por pendência e lista o empréstimo em atraso lido da API', async () => {
    rerender(reservable);
    const base = { author: 'X', cover_url: null, queue_position: null, available_since: null, expires_at: null };
    tracking.getLoans.and.returnValue(of([
      { ...base, id: 1, book_id: 9, title: '1984', status: 'OVERDUE', copy_barcode: '00402', due_date: '2026-09-15', pickup_date: '2026-08-15', days_late: 5 },
      { ...base, id: 2, book_id: 8, title: 'Em dia', status: 'ACTIVE', copy_barcode: '1', due_date: '2026-12-15', pickup_date: '2026-11-15', days_late: 0 },
    ] as any));
    requests.reservePurchase.and.returnValue(throwError(() => domainBlock));
    await click('Reservar compra'); await click('Confirmar reserva');
    expect(root().textContent).toContain('Reserva bloqueada por pendência');
    expect(root().textContent).toContain('Não foi possível registrar a reserva');
    expect(root().textContent).toContain('Cliente inativo, penalizado ou com empréstimo em atraso.');
    expect(root().textContent).toContain('Empréstimo de 1984 · Exemplar #00402');
    expect(root().textContent).toContain('Devolução prevista: 15/09/2026 · em atraso');
    expect(root().textContent).not.toContain('Em dia');
    expect(root().querySelector('.snackbar')).toBeNull();
    expect(root().querySelector('a[href="/meus-emprestimos"]')).not.toBeNull();
    await click('Voltar ao livro');
    expect(root().textContent).toContain('Disponibilidade');
  });

  it('mostra o bloqueio mesmo sem empréstimo em atraso, sem inventar detalhes', async () => {
    requests.requestLoan.and.returnValue(throwError(() => domainBlock));
    setDate(todayInSaoPaulo()); await submit();
    expect(root().textContent).toContain('Solicitação bloqueada por pendência');
    expect(root().textContent).toContain('Não foi possível registrar a solicitação de empréstimo');
    expect(root().textContent).not.toContain('Exemplar #');
    expect(root().textContent).toContain('tente solicitar novamente');
    await click('Voltar ao livro');
    expect(root().querySelector<HTMLInputElement>('#pickup-date')!.value).toBe(todayInSaoPaulo());
  });

  it('solicitação de empréstimo duplicada não vira sucesso e leva a Meus empréstimos', async () => {
    requests.requestLoan.and.returnValue(throwError(() => ({ detail: 'Você já possui uma solicitação pendente para este livro.', code: 'loan_request_duplicate', status: 409 })));
    setDate(todayInSaoPaulo()); await submit();
    expect(root().textContent).toContain('Você já possui uma solicitação pendente');
    expect(root().querySelector('a[href="/meus-emprestimos"]')).not.toBeNull();
    expect(root().querySelector('.snackbar')).toBeNull();
  });

  it('mantém a consulta local não configurada sem texto de regra inexistente', () => {
    const text = root().querySelectorAll('details')[2].textContent!;
    expect(text).toContain('Consulta local não configurada');
    expect(text).not.toContain('Entre em contato');
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
