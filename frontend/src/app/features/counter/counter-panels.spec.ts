import { Provider, Type } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../app.routes';
import { CounterService, StaffClient, StaffLoan, StaffLoanRequest, StaffPurchaseReservation } from './counter.service';
import { ClientsPanelComponent } from './clients-panel.component';
import { businessToday } from './business-date';
import { CounterContext } from './counter-context.service';
import { CounterClientsPageComponent } from './counter-pages';
import { PickupsPanelComponent } from './pickups-panel.component';
import { ReservationsPanelComponent } from './reservations-panel.component';

const client = (over: Partial<StaffClient> = {}): StaffClient => ({
  id: 3, name: 'Ana Souza', email: 'ana@x.dev', is_active: true, is_penalized: false,
  has_overdue_loan: false, eligible: true, ...over,
});
const book = { id: 10, title: 'Dom Casmurro', author: 'Machado de Assis', is_active: true };

const loanRequest = (over: Partial<StaffLoanRequest> = {}): StaffLoanRequest => ({
  id: 11, client: client(), book, pickup_date: '2026-10-05', due_date: '2026-11-05', created_at: '2026-10-01T12:00:00Z',
  eligible_copies: [{ id: 91, barcode: 'D-001', condition: 'GOOD' }, { id: 92, barcode: 'D-002', condition: null }], ...over,
});

const loan = (over: Partial<StaffLoan> = {}): StaffLoan => ({
  id: 21, client: client(), book, copy_id: 91, copy_barcode: 'D-001', loan_date: '2026-09-01T12:00:00Z',
  due_date: '2026-10-01T12:00:00Z', status: 'OVERDUE', days_late: 2, ...over,
});

const reservation = (over: Partial<StaffPurchaseReservation> = {}): StaffPurchaseReservation => ({
  id: 31, client: client(), book, status: 'WAITING', queue_position: 1, requested_at: '2026-10-01T12:00:00Z',
  pickup_date: null, notified_at: null, expires_at: null, expired: false, allocated_copy_id: null,
  allocated_copy_barcode: null, free_commercial_copies: 1, can_allocate: true, allocation_blocked_reason: null, ...over,
});

type Spies = {
  [K in keyof CounterService]: jasmine.Spy;
};

function setup<T>(component: Type<T>, configure: (service: Spies) => void = () => undefined, extra: Provider[] = []) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', [
    'searchClients', 'getClientPendencies', 'listLoanRequests', 'confirmPickup', 'listLoans', 'confirmReturn',
    'listPurchaseReservations', 'allocatePurchase', 'confirmSale',
  ]) as unknown as Spies;
  configure(service);
  TestBed.configureTestingModule({ imports: [component], providers: [provideRouter([]), { provide: CounterService, useValue: service }, ...extra] });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

function button(root: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`Botão não encontrado: ${label}`);
  return found as HTMLButtonElement;
}

function click(fixture: ComponentFixture<unknown>, element: HTMLElement) {
  element.click();
  fixture.detectChanges();
}

function dialog(root: HTMLElement): HTMLDialogElement | null {
  return root.querySelector('dialog');
}

describe('Balcão: retiradas', () => {
  it('mostra carregamento e depois o estado vazio', () => {
    const pending = new Subject<StaffLoanRequest[]>();
    const { fixture, root } = setup(PickupsPanelComponent, (s) => s.listLoanRequests.and.returnValue(pending));
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Carregando');
    pending.next([]);
    fixture.detectChanges();
    expect(root.textContent).toContain('Nenhuma solicitação de empréstimo pendente.');
  });

  it('diferencia falha de consulta de lista vazia e permite tentar de novo', () => {
    const { fixture, root, service } = setup(PickupsPanelComponent, (s) =>
      s.listLoanRequests.and.returnValue(throwError(() => ({ detail: 'Cadastro de funcionário ativo necessário.' }))));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Cadastro de funcionário ativo necessário.');
    expect(root.textContent).not.toContain('Nenhuma solicitação');
    service.listLoanRequests.and.returnValue(of([]));
    click(fixture, button(root, 'Tentar novamente'));
    expect(root.textContent).toContain('Nenhuma solicitação de empréstimo pendente.');
  });

  it('exige exemplar selecionado e pede confirmação antes do POST', () => {
    const { fixture, root, service } = setup(PickupsPanelComponent, (s) => s.listLoanRequests.and.returnValue(of([loanRequest()])));
    expect(root.textContent).toContain('Ana Souza');
    expect(root.textContent).toContain('Dom Casmurro');
    const confirm = button(root, 'Confirmar retirada');
    expect(confirm.disabled).toBeTrue();
    const select = root.querySelector('select') as HTMLSelectElement;
    select.value = '92'; select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(confirm.disabled).toBeFalse();
    click(fixture, confirm);
    expect(service.confirmPickup).not.toHaveBeenCalled();
    expect(dialog(root)?.textContent).toContain('D-002');
    expect(dialog(root)?.getAttribute('aria-labelledby')).toBeTruthy();
    click(fixture, button(root, 'Cancelar'));
    expect(dialog(root)).toBeNull();
    expect(service.confirmPickup).not.toHaveBeenCalled();
  });

  it('bloqueia envio duplicado, só anuncia sucesso após a resposta e recarrega a lista', () => {
    const response = new Subject<{ id: number }>();
    const { fixture, root, service } = setup(PickupsPanelComponent, (s) => {
      s.listLoanRequests.and.returnValue(of([loanRequest()]));
      s.confirmPickup.and.returnValue(response);
    });
    const select = root.querySelector('select') as HTMLSelectElement;
    select.value = '91'; select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    click(fixture, button(root, 'Confirmar retirada'));
    const submit = dialog(root)!.querySelector('.confirm__submit') as HTMLButtonElement;
    click(fixture, submit);
    click(fixture, submit);
    expect(service.confirmPickup).toHaveBeenCalledOnceWith(11, 91);
    expect(submit.disabled).toBeTrue();
    expect(submit.getAttribute('aria-busy')).toBe('true');
    expect(root.textContent).not.toContain('Retirada confirmada');
    service.listLoanRequests.and.returnValue(of([]));
    response.next({ id: 77 }); response.complete();
    fixture.detectChanges();
    expect(dialog(root)).toBeNull();
    expect(root.querySelector('[data-feedback]')?.textContent).toContain('Retirada confirmada. Empréstimo #77');
    expect(service.listLoanRequests).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain('Nenhuma solicitação de empréstimo pendente.');
  });

  it('mostra o erro de domínio, não mostra sucesso e recarrega', () => {
    const { fixture, root, service } = setup(PickupsPanelComponent, (s) => {
      s.listLoanRequests.and.returnValue(of([loanRequest()]));
      s.confirmPickup.and.returnValue(throwError(() => ({ detail: 'A retirada desta solicitação já foi confirmada.', code: 'pickup_already_confirmed', status: 409 })));
    });
    const select = root.querySelector('select') as HTMLSelectElement;
    select.value = '91'; select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    click(fixture, button(root, 'Confirmar retirada'));
    click(fixture, dialog(root)!.querySelector('.confirm__submit') as HTMLElement);
    const feedback = root.querySelector('[data-feedback]')!;
    expect(feedback.querySelector('[role="alert"]')?.textContent).toContain('já foi confirmada');
    expect(feedback.textContent).not.toContain('Retirada confirmada.');
    expect(service.listLoanRequests).toHaveBeenCalledTimes(2);
  });

  it('não permite confirmar para cliente inelegível ou sem exemplar', () => {
    const { root } = setup(PickupsPanelComponent, (s) => s.listLoanRequests.and.returnValue(of([
      loanRequest({ client: client({ eligible: false, is_penalized: true }) }),
      loanRequest({ id: 12, eligible_copies: [] }),
    ])));
    expect(root.textContent).toContain('Cliente inelegível (penalizado)');
    expect(root.textContent).toContain('Nenhum exemplar didático disponível');
    root.querySelectorAll('button').forEach((b) => {
      if (b.textContent?.trim() === 'Confirmar retirada') expect(b.disabled).toBeTrue();
    });
  });

  it('segue o frame: título, busca por e-mail, "Sem pendências" e linha da obra com exemplar e data', () => {
    const today = businessToday();
    const { root } = setup(PickupsPanelComponent, (s) => s.listLoanRequests.and.returnValue(of([
      loanRequest({ pickup_date: today, eligible_copies: [{ id: 91, barcode: '00101', condition: null }] }),
    ])));
    expect(root.querySelector('h1')?.textContent).toBe('Solicitações de empréstimo');
    expect(root.querySelector('.page__back')?.textContent).toContain('← Empréstimos');
    expect((root.querySelector('#pickup-q') as HTMLInputElement).placeholder).toBe('Buscar cliente por e-mail cadastrado');
    expect(root.querySelector('.eyebrow')?.textContent).toBe('RETIRADAS DE HOJE');
    const card = root.querySelector('.request')!;
    expect(card.querySelector('h3')?.textContent).toBe('Ana Souza');
    expect(card.querySelector('.request__client')?.textContent).toContain('ana@x.dev');
    expect(card.querySelector('.request__client')?.textContent).toContain('Sem pendências');
    expect(card.querySelector('.request__book')?.textContent).toContain('Dom Casmurro');
    expect(card.querySelector('.request__book')?.textContent).toContain('Exemplar #00101');
    expect(card.querySelector('.request__book')?.textContent).toMatch(/Retirada: \d{2}\/\d{2}\/\d{4}/);
    expect(card.querySelector('select')).toBeNull();  // exemplar único: nada a escolher
    expect((button(root, 'Confirmar retirada')).disabled).toBeFalse();
  });

  it('separa as retiradas de hoje das demais solicitações pendentes e informa a pendência do cliente', () => {
    const today = businessToday();
    const { root } = setup(PickupsPanelComponent, (s) => s.listLoanRequests.and.returnValue(of([
      loanRequest({ id: 1, pickup_date: '2000-01-01' }),
      loanRequest({ id: 2, pickup_date: today, client: client({ eligible: false, has_overdue_loan: true }) }),
    ])));
    expect(Array.from(root.querySelectorAll('.eyebrow')).map((e) => e.textContent)).toEqual(['RETIRADAS DE HOJE', 'OUTRAS SOLICITAÇÕES']);
    expect(root.querySelector('.request__client')?.textContent).toContain('Empréstimo em atraso');
  });

  it('aplica o filtro de cliente vindo da aba de clientes', () => {
    const { fixture, service } = setup(PickupsPanelComponent, (s) => s.listLoanRequests.and.returnValue(of([])));
    expect(service.listLoanRequests).toHaveBeenCalledWith({ q: '', clientId: undefined });
    fixture.componentRef.setInput('client', client());
    fixture.detectChanges();
    expect(service.listLoanRequests).toHaveBeenCalledWith({ q: '', clientId: 3 });
  });
});

describe('Balcão: reservas de compra', () => {
  it('permite destinar exemplar à primeira reserva e confirma antes de enviar', () => {
    const { fixture, root, service } = setup(ReservationsPanelComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([reservation()]));
      s.allocatePurchase.and.returnValue(of({ id: 31 }));
    });
    expect(root.textContent).toContain('1º');
    click(fixture, button(root, 'Destinar exemplar'));
    expect(service.allocatePurchase).not.toHaveBeenCalled();
    click(fixture, dialog(root)!.querySelector('.confirm__submit') as HTMLElement);
    expect(service.allocatePurchase).toHaveBeenCalledOnceWith(10);
    expect(root.querySelector('[data-feedback]')?.textContent).toContain('Exemplar destinado a Ana Souza');
  });

  it('explica o bloqueio quando o primeiro da fila está inelegível, sem saltar a fila', () => {
    const { root } = setup(ReservationsPanelComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      reservation({ can_allocate: false, allocation_blocked_reason: 'CLIENT_INELIGIBLE', client: client({ eligible: false, has_overdue_loan: true }) }),
      reservation({ id: 32, queue_position: 2, can_allocate: false, allocation_blocked_reason: 'NOT_FIRST_IN_QUEUE' }),
    ])));
    expect(root.textContent).toContain('não pula a fila');
    expect(root.textContent).toContain('só a primeira reserva da fila recebe exemplar');
    root.querySelectorAll('button').forEach((b) => {
      if (b.textContent?.trim() === 'Destinar exemplar') expect(b.disabled).toBeTrue();
    });
  });

  it('mostra exemplar destinado sem inventar prazo e confirma a venda', () => {
    const notified = reservation({ status: 'NOTIFIED', queue_position: null, allocated_copy_id: 55, allocated_copy_barcode: 'C-055',
      notified_at: '2026-10-03T12:00:00Z', can_allocate: false, free_commercial_copies: 0 });
    const { fixture, root, service } = setup(ReservationsPanelComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([notified]));
      s.confirmSale.and.returnValue(of({ id: 5 }));
    });
    expect(root.textContent).toContain('C-055');
    expect(root.textContent).not.toContain('Retirar até');
    click(fixture, button(root, 'Confirmar venda'));
    click(fixture, dialog(root)!.querySelector('.confirm__submit') as HTMLElement);
    expect(service.confirmSale).toHaveBeenCalledOnceWith(31);
    expect(root.querySelector('[data-feedback]')?.textContent).toContain('Venda #5 confirmada');
  });

  it('desabilita a venda de reserva expirada e informa a limitação', () => {
    const { root } = setup(ReservationsPanelComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      reservation({ status: 'NOTIFIED', allocated_copy_id: 55, allocated_copy_barcode: 'C-055', expired: true, expires_at: '2026-09-01T12:00:00Z', can_allocate: false }),
    ])));
    expect(button(root, 'Confirmar venda').disabled).toBeTrue();
    expect(root.textContent).toContain('Prazo de retirada expirado');
  });

  it('desabilita a venda para cliente inelegível ou obra inativa', () => {
    const base = { status: 'NOTIFIED' as const, allocated_copy_id: 55, allocated_copy_barcode: 'C-055', can_allocate: false };
    const { root } = setup(ReservationsPanelComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      reservation({ ...base, client: client({ eligible: false, is_penalized: true }) }),
      reservation({ ...base, id: 32, book: { ...book, is_active: false } }),
    ])));
    root.querySelectorAll('button').forEach((b) => {
      if (b.textContent?.trim() === 'Confirmar venda') expect(b.disabled).toBeTrue();
    });
  });

  it('avisa quando a lista atinge o limite e pode estar truncada', () => {
    const many = Array.from({ length: 50 }, (_, i) => reservation({ id: i + 1 }));
    const { root } = setup(ReservationsPanelComponent, (s) => s.listPurchaseReservations.and.returnValue(of(many)));
    expect(root.textContent).toContain('Mostrando os primeiros 50 resultados. Refine a busca');
  });

  it('não avisa de truncamento abaixo do limite', () => {
    const { root } = setup(ReservationsPanelComponent, (s) => s.listPurchaseReservations.and.returnValue(of([reservation()])));
    expect(root.textContent).not.toContain('Mostrando os primeiros');
  });

  it('filtra por situação', () => {
    const { fixture, root, service } = setup(ReservationsPanelComponent, (s) => s.listPurchaseReservations.and.returnValue(of([])));
    const select = root.querySelector('#reservation-status') as HTMLSelectElement;
    select.value = 'NOTIFIED'; select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(service.listPurchaseReservations.calls.mostRecent().args[0]).toEqual({ q: '', clientId: undefined, status: 'NOTIFIED' });
  });
});

describe('Balcão: clientes e navegação', () => {
  function search(fixture: ComponentFixture<unknown>, root: HTMLElement, term: string) {
    const input = root.querySelector('#client-q') as HTMLInputElement;
    input.value = term; input.dispatchEvent(new Event('input'));
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('não consulta com termo curto e orienta o funcionário', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent);
    search(fixture, root, ' a ');
    expect(service.searchClients).not.toHaveBeenCalled();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('ao menos 2 caracteres');
  });

  it('lista clientes, seleciona e consulta pendências', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent, (s) => {
      s.searchClients.and.returnValue(of([client(), client({ id: 4, name: 'Bia', eligible: false, has_overdue_loan: true })]));
      s.getClientPendencies.and.returnValue(of({ client: client({ id: 4, is_penalized: true, eligible: false }),
        overdue_loans: [loan({ id: 1, days_late: 3 })] }));
    });
    search(fixture, root, 'an');
    expect(service.searchClients).toHaveBeenCalledOnceWith('an');
    expect(root.textContent).toContain('Inelegível: empréstimo em atraso');
    click(fixture, root.querySelectorAll<HTMLButtonElement>('button')[5]);
    expect(service.getClientPendencies).toHaveBeenCalledOnceWith(4);
    expect(root.textContent).toContain('Empréstimos em atraso: 1');
    expect(root.textContent).toContain('Cliente penalizado');
    expect(root.textContent).toContain('3 dia(s) de atraso');
  });

  it('avisa quando a busca de clientes atinge o limite', () => {
    const many = Array.from({ length: 20 }, (_, i) => client({ id: i + 1 }));
    const { fixture, root } = setup(ClientsPanelComponent, (s) => s.searchClients.and.returnValue(of(many)));
    search(fixture, root, 'an');
    expect(root.textContent).toContain('Mostrando os primeiros 20 resultados');
  });

  it('mostra vazio e erro de busca de forma distinta', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent, (s) => s.searchClients.and.returnValue(of([])));
    search(fixture, root, 'zz');
    expect(root.textContent).toContain('Nenhum cliente encontrado');
    service.searchClients.and.returnValue(throwError(() => ({ detail: 'Permissão insuficiente.' }) ));
    search(fixture, root, 'zzz');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Permissão insuficiente.');
  });

  it('abre a tela escolhida guardando o cliente como filtro', () => {
    const router = jasmine.createSpyObj<Router>('Router', ['navigateByUrl']);
    const { fixture, root } = setup(CounterClientsPageComponent, (s) => s.searchClients.and.returnValue(of([client()])),
      [{ provide: Router, useValue: router }]);
    search(fixture, root, 'ana');
    click(fixture, button(root, 'Empréstimos'));
    expect(TestBed.inject(CounterContext).client()?.id).toBe(3);
    expect(router.navigateByUrl).toHaveBeenCalledOnceWith('/balcao/emprestimos/ativos');
    click(fixture, button(root, 'Solicitações'));
    expect(router.navigateByUrl).toHaveBeenCalledWith('/balcao/emprestimos/solicitacoes');
    click(fixture, button(root, 'Reservas'));
    expect(router.navigateByUrl).toHaveBeenCalledWith('/balcao/reservas');
  });
});

describe('Rotas do balcão', () => {
  const counter = routes.find((r) => r.path === 'balcao');

  it('é protegida por autenticação e restrita a SELLER e ADMINISTRATOR', () => {
    expect(counter?.canActivate?.length).toBe(2);
    expect(counter?.data?.['roles']).toEqual(['SELLER', 'ADMINISTRATOR']);
  });

  it('declara as telas do funcionário como rotas filhas do layout', () => {
    const paths = counter?.children?.map((r) => r.path);
    expect(paths).toEqual(jasmine.arrayContaining(['clientes', 'emprestimos/solicitacoes', 'emprestimos/ativos', 'devolucoes', 'vendas']));
  });
});
