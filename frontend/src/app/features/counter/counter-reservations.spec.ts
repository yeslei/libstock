import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { Type } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { CounterReservationAttendComponent } from './counter-reservation-attend.component';
import { CounterReservationsComponent } from './counter-reservations.component';
import { CounterContext } from './counter-context.service';
import { CounterService, StaffClient, StaffPurchaseReservation } from './counter.service';
import { canSellReservation, groupByBook } from './reservation-queue';

const client = (over: Partial<StaffClient> = {}): StaffClient => ({
  id: 3, name: 'Maria Silva', email: 'maria@x.dev', is_active: true, is_penalized: false,
  has_overdue_loan: false, eligible: true, ...over,
});
const book = { id: 10, title: 'Dom Casmurro', author: 'Machado de Assis', is_active: true };

const waiting = (over: Partial<StaffPurchaseReservation> = {}): StaffPurchaseReservation => ({
  id: 32, client: client({ id: 4, name: 'Ana Santos', email: 'ana@x.dev' }), book, status: 'WAITING', queue_position: 1,
  requested_at: '2026-10-01T12:00:00Z', pickup_date: null, notified_at: null, expires_at: null, expired: false,
  allocated_copy_id: null, allocated_copy_barcode: null, free_commercial_copies: 1, can_allocate: true,
  allocation_blocked_reason: null, ...over,
});

const notified = (over: Partial<StaffPurchaseReservation> = {}): StaffPurchaseReservation => ({
  ...waiting({ id: 31, client: client() }), status: 'NOTIFIED', queue_position: null, notified_at: '2026-10-03T12:00:00Z',
  allocated_copy_id: 55, allocated_copy_barcode: 'C-055', free_commercial_copies: 0, can_allocate: false, ...over,
});

type Spies = { [K in keyof CounterService]: jasmine.Spy };

function create<T>(component: Type<T>, configure: (service: Spies) => void, inputs: Record<string, unknown> = {}) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', [
    'listPurchaseReservations', 'allocatePurchase', 'confirmSale', 'cancelReservation', 'expireDueReservations',
  ]) as unknown as Spies;
  configure(service);
  TestBed.configureTestingModule({ imports: [component], providers: [provideRouter([]), { provide: CounterService, useValue: service }] });
  const fixture = TestBed.createComponent(component);
  for (const [name, value] of Object.entries(inputs)) fixture.componentRef.setInput(name, value);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

function press(fixture: ComponentFixture<unknown>, element: HTMLElement) {
  element.click();
  fixture.detectChanges();
}

function button(root: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`Botão não encontrado: ${label}`);
  return found as HTMLButtonElement;
}

function link(root: HTMLElement, label: string): HTMLAnchorElement | undefined {
  return Array.from(root.querySelectorAll('a')).find((a) => a.textContent?.trim() === label);
}

function typeInto(fixture: ComponentFixture<unknown>, input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event('input'));
  fixture.detectChanges();
}

function submit(fixture: ComponentFixture<unknown>, root: HTMLElement) {
  root.querySelector('form')!.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

describe('Fila de reservas (agrupamento)', () => {
  it('agrupa por obra e coloca a reserva com exemplar destinado antes das aguardando', () => {
    const other = waiting({ id: 40, book: { ...book, id: 11, title: 'Iracema' }, queue_position: 1 });
    const groups = groupByBook([waiting({ id: 33, queue_position: 2 }), waiting(), notified(), other]);
    expect(groups.map((g) => g.title)).toEqual(['Dom Casmurro', 'Iracema']);
    expect(groups[0].entries.map((r) => r.id)).toEqual([31, 32, 33]);
  });

  it('só permite a venda com exemplar destinado, cliente elegível, obra ativa e dentro do prazo', () => {
    expect(canSellReservation(notified())).toBeTrue();
    expect(canSellReservation(waiting())).toBeFalse();
    expect(canSellReservation(notified({ expired: true }))).toBeFalse();
    expect(canSellReservation(notified({ client: client({ eligible: false }) }))).toBeFalse();
    expect(canSellReservation(notified({ book: { ...book, is_active: false } }))).toBeFalse();
  });
});

describe('Balcão: lista de reservas de compra', () => {
  const dialog = (root: HTMLElement) => root.querySelector('dialog');

  it('mostra a fila por obra com posições, exemplar destinado e o prazo persistido', () => {
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      waiting(), notified({ expires_at: '2026-10-06T12:00:00Z' }),
    ])));
    expect(root.querySelector('h1')?.textContent).toBe('Reservas de compra');
    expect(root.querySelector('h2')?.textContent).toBe('Dom Casmurro · Fila de compra');
    expect(root.textContent).toContain('Maria Silva · Disponível para retirada · Exemplar C-055');
    expect(root.textContent).toContain('Retirar até 06/10/2026');
    expect(root.textContent).toContain('1ª · Ana Santos · Aguardando disponibilidade');
    const attend = link(root, 'Atender Maria Silva')!;
    expect(attend.getAttribute('href')).toBe('/balcao/reservas/31?cliente=3');
  });

  it('não inventa prazo quando o backend não informa expires_at', () => {
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified()])));
    expect(root.textContent).not.toContain('Prazo de retirada:');
  });

  it('sinaliza reserva expirada pelo backend sem oferecer "Atender"', () => {
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      notified({ expired: true, expires_at: '2026-09-01T12:00:00Z' }),
    ])));
    expect(root.textContent).toContain('Prazo de retirada encerrado');
    expect(link(root, 'Atender Maria Silva')).toBeUndefined();
    expect(link(root, 'Ver reserva de Maria Silva')).toBeDefined();
  });

  it('destina exemplar à primeira da fila somente após confirmar e mostra o sucesso depois do 2xx', () => {
    const response = new Subject<{ id: number }>();
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([waiting()]));
      s.allocatePurchase.and.returnValue(response);
    });
    press(fixture, button(root, 'Destinar exemplar a Ana Santos'));
    expect(service.allocatePurchase).not.toHaveBeenCalled();
    const confirmButton = dialog(root)!.querySelector('.confirm__submit') as HTMLButtonElement;
    press(fixture, confirmButton);
    press(fixture, confirmButton);
    expect(service.allocatePurchase).toHaveBeenCalledOnceWith(10);
    expect(snackbarMessage()).not.toContain('Exemplar destinado');
    response.next({ id: 32 });
    response.complete();
    fixture.detectChanges();
    expect(snackbarMessage()).toContain('Exemplar destinado a Ana Santos');
    expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
  });

  it('mostra o erro de domínio e recarrega quando a destinação falha', () => {
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([waiting()]));
      s.allocatePurchase.and.returnValue(throwError(() => ({ detail: 'Não há exemplar comercial livre para esta operação.', code: 'purchase_unavailable', status: 409 })));
    });
    press(fixture, button(root, 'Destinar exemplar a Ana Santos'));
    press(fixture, dialog(root)!.querySelector('.confirm__submit') as HTMLElement);
    expect(snackbarMessage()).toContain('Não há exemplar comercial livre');
    expect(snackbarMessage()).not.toContain('Exemplar destinado');
    expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
  });

  it('explica o bloqueio do primeiro inelegível mantendo a posição e sem oferecer a destinação a ele', () => {
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      waiting({ can_allocate: false, allocation_blocked_reason: 'CLIENT_INELIGIBLE', client: client({ eligible: false, has_overdue_loan: true }) }),
      waiting({ id: 33, queue_position: 2, can_allocate: false, allocation_blocked_reason: 'NOT_FIRST_ELIGIBLE' }),
    ])));
    expect(root.textContent).toContain('Mantém a posição na fila');
    expect(root.textContent).not.toContain('Destinar exemplar a');
  });

  it('mostra "Nenhuma reserva encontrada" para busca vazia e limpa a busca', () => {
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValues(of([]), of([]), of([waiting()])));
    expect(root.textContent).toContain('Nenhuma reserva de compra em andamento.');
    typeInto(fixture, root.querySelector('#reservation-q') as HTMLInputElement, 'Dom Casmurro');
    submit(fixture, root);
    expect(service.listPurchaseReservations.calls.mostRecent().args[0]).toEqual({ q: 'Dom Casmurro', clientId: undefined });
    expect(root.textContent).toContain('Nenhuma reserva corresponde à busca');
    expect(link(root, 'Voltar ao painel')?.getAttribute('href')).toBe('/balcao/painel');
    press(fixture, button(root, 'Limpar busca'));
    expect(service.listPurchaseReservations.calls.mostRecent().args[0]).toEqual({ q: '', clientId: undefined });
    expect((root.querySelector('#reservation-q') as HTMLInputElement).value).toBe('');
    expect(root.textContent).toContain('Fila de compra');
  });

  it('usa o cliente escolhido em Clientes como filtro e permite removê-lo', () => {
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([waiting()])));
    TestBed.inject(CounterContext).client.set(client());
    fixture.componentInstance['reload']();
    fixture.detectChanges();
    expect(service.listPurchaseReservations.calls.mostRecent().args[0]).toEqual({ q: '', clientId: 3 });
    expect(root.querySelector('.chip')?.textContent).toContain('Cliente: Maria Silva');
    press(fixture, button(root, 'Remover filtro'));
    expect(service.listPurchaseReservations.calls.mostRecent().args[0]).toEqual({ q: '', clientId: undefined });
  });

  it('mostra erro de consulta com nova tentativa', () => {
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValues(
      throwError(() => ({ detail: 'Falhou', status: 500 })), of([waiting()])));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Falhou');
    press(fixture, button(root, 'Tentar novamente'));
    expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain('Dom Casmurro · Fila de compra');
  });

  it('avisa quando a lista atinge o limite e pode estar truncada', () => {
    const many = Array.from({ length: 50 }, (_, i) => waiting({ id: i + 1 }));
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of(many)));
    expect(root.textContent).toContain('Mostrando os primeiros 50 resultados. Refine a busca');
  });
});

describe('Balcão: atender reserva', () => {
  const inputs = { id: '31', cliente: '3' };
  const code = (root: HTMLElement) => root.querySelector('#copy-code') as HTMLInputElement;

  it('carrega a reserva do cliente e mostra os dados e o exemplar destinado', () => {
    const { root, service } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified({ expires_at: '2026-10-06T12:00:00Z' })])), inputs);
    expect(service.listPurchaseReservations).toHaveBeenCalledOnceWith({ clientId: 3 });
    expect(root.querySelector('h1')?.textContent).toBe('Atender reserva');
    expect(root.querySelector('h2')?.textContent).toBe('Reserva de Maria Silva');
    expect(root.textContent).toContain('maria@x.dev · conta ativa · sem pendências');
    expect(root.textContent).toContain('Exemplar C-055 · Comercial · destinado à venda');
    expect(root.textContent).toContain('Retirar até 06/10/2026');
  });

  it('exige o código e recusa um código diferente do exemplar destinado, sem avançar', () => {
    const { fixture, root, service } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified()])), inputs);
    press(fixture, button(root, 'Conferir venda'));
    expect(root.querySelector('#copy-code-error')?.textContent).toContain('Informe o código');
    typeInto(fixture, code(root), 'C-999');
    press(fixture, button(root, 'Conferir venda'));
    expect(root.querySelector('#copy-code-error')?.textContent).toContain('não corresponde ao exemplar destinado');
    expect(code(root).getAttribute('aria-invalid')).toBe('true');
    expect(root.querySelector('h1')?.textContent).toBe('Atender reserva');
    expect(service.confirmSale).not.toHaveBeenCalled();
  });

  it('confere o código, mostra o resumo e só conclui após o 2xx, com envio duplicado bloqueado', () => {
    const response = new Subject<{ id: number }>();
    const { fixture, root, service } = create(CounterReservationAttendComponent, (s) => {
      s.listPurchaseReservations.and.returnValues(of([notified()]), of([waiting(), waiting({ id: 33, queue_position: 2 })]));
      s.confirmSale.and.returnValue(response);
    }, inputs);
    typeInto(fixture, code(root), ' C-055 ');
    press(fixture, button(root, 'Conferir venda'));
    expect(root.querySelector('h1')?.textContent).toBe('Confirmar venda da reserva');
    expect(root.textContent).toContain('Cliente: Maria Silva · maria@x.dev');
    expect(root.textContent).toContain('Livro: Dom Casmurro · Exemplar C-055');
    expect(root.textContent).toContain('o exemplar ficará Vendido');
    expect(service.confirmSale).not.toHaveBeenCalled();
    const confirm = button(root, 'Confirmar venda');
    press(fixture, confirm);
    press(fixture, confirm);
    expect(service.confirmSale).toHaveBeenCalledOnceWith(31);
    expect(root.querySelector('h1')?.textContent).toBe('Confirmar venda da reserva');
    expect(root.textContent).not.toContain('Venda registrada com sucesso');
    expect(button(root, 'Voltar').disabled).toBeTrue();
    response.next({ id: 9 });
    response.complete();
    fixture.detectChanges();
    expect(root.querySelector('h1')?.textContent).toBe('Venda da reserva concluída');
    expect(root.textContent).toContain('Venda registrada com sucesso');
    expect(root.textContent).toContain('A reserva de Maria Silva foi concluída.');
    expect(root.textContent).toContain('Dom Casmurro · Exemplar C-055 · Vendido');
    expect(root.textContent).toContain('Venda nº 9');
    expect(root.textContent).toContain('Ana Santos passa à 1ª posição');
    expect(link(root, 'Voltar à fila')?.getAttribute('href')).toBe('/balcao/reservas');
    expect(link(root, 'Registrar outra venda')?.getAttribute('href')).toBe('/balcao/vendas');
  });

  it('volta da confirmação para a conferência sem enviar nada', () => {
    const { fixture, root, service } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified()])), inputs);
    typeInto(fixture, code(root), 'C-055');
    press(fixture, button(root, 'Conferir venda'));
    press(fixture, button(root, 'Voltar'));
    expect(root.querySelector('h1')?.textContent).toBe('Atender reserva');
    expect(service.confirmSale).not.toHaveBeenCalled();
  });

  it('falha 5xx ao confirmar a venda mostra "Não foi possível salvar" sem snackbar e sem reenvio', () => {
    const { fixture, root, service } = create(CounterReservationAttendComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([notified()]));
      s.confirmSale.and.returnValue(throwError(() => ({ status: 500, detail: 'Tivemos um problema no servidor.' })));
    }, inputs);
    typeInto(fixture, code(root), 'C-055');
    press(fixture, button(root, 'Conferir venda'));
    press(fixture, button(root, 'Confirmar venda'));
    expect(root.querySelector('app-save-failure')?.textContent).toContain('Não foi possível salvar');
    expect(snackbarMessage()).toBe('');
    expect(root.textContent).not.toContain('Venda da reserva concluída');
    expect(service.confirmSale).toHaveBeenCalledTimes(1);
    press(fixture, button(root, 'Voltar'));
    expect(root.querySelector('app-save-failure')).toBeNull();
  });

  for (const [codeName, message] of [
    ['reservation_expired', 'O prazo de retirada desta reserva expirou.'],
    ['reservation_not_ready', 'Esta reserva ainda não tem exemplar destinado para retirada.'],
    ['client_ineligible', 'O cliente está inativo, penalizado ou com empréstimo em atraso.'],
  ] as const) {
    it(`mostra o erro ${codeName} sem anunciar sucesso e recarrega a reserva`, () => {
      const { fixture, root, service } = create(CounterReservationAttendComponent, (s) => {
        s.listPurchaseReservations.and.returnValue(of([notified()]));
        s.confirmSale.and.returnValue(throwError(() => ({ detail: message, code: codeName, status: 409 })));
      }, inputs);
      typeInto(fixture, code(root), 'C-055');
      press(fixture, button(root, 'Conferir venda'));
      press(fixture, button(root, 'Confirmar venda'));
      expect(snackbarMessage()).toContain(message);
      expect(snackbarVariant()).toBe('warning');
      expect(root.textContent).not.toContain('Venda registrada com sucesso');
      expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
      expect(button(root, 'Confirmar venda').disabled).toBeFalse();
    });
  }

  it('mostra "Reserva fora do prazo" apenas quando o backend informa expired', () => {
    const { root } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      notified({ expired: true, expires_at: '2026-09-01T12:00:00Z' }),
    ])), inputs);
    expect(root.querySelector('h1')?.textContent).toBe('Reserva fora do prazo');
    expect(root.textContent).toContain('Maria Silva · Dom Casmurro · Exemplar C-055');
    expect(root.textContent).toContain('Prazo de retirada encerrado em 01/09/2026');
    expect(root.textContent).toContain('Esta reserva não pode ser atendida como prioridade ativa.');
    expect(link(root, 'Consultar fila')?.getAttribute('href')).toBe('/balcao/reservas');
    expect(root.querySelector('#copy-code')).toBeNull();
  });

  it('com prazo no futuro ou sem prazo informado não mostra o estado fora do prazo', () => {
    const { root } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      notified({ expires_at: '2099-01-01T12:00:00Z', expired: false }),
    ])), inputs);
    expect(root.querySelector('h1')?.textContent).toBe('Atender reserva');
  });

  it('bloqueia a conferência quando o cliente está inelegível', () => {
    const { root } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      notified({ client: client({ eligible: false, is_penalized: true }) }),
    ])), inputs);
    expect(root.textContent).toContain('penalizado');
    expect(root.textContent).toContain('A venda não pode ser confirmada');
    expect(button(root, 'Conferir venda').disabled).toBeTrue();
    expect(code(root).disabled).toBeTrue();
  });

  it('informa reserva sem exemplar destinado e reserva inexistente', () => {
    const first = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([waiting({ id: 31 })])), inputs);
    expect(first.root.textContent).toContain('Reserva sem exemplar destinado');
    TestBed.resetTestingModule();
    const second = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([])), inputs);
    expect(second.root.querySelector('h1')?.textContent).toBe('Reserva não encontrada');
    expect(link(second.root, 'Voltar às reservas')?.getAttribute('href')).toBe('/balcao/reservas');
  });

  it('recarrega a reserva pela URL e trata erro de consulta com nova tentativa', () => {
    const { fixture, root, service } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValues(
      throwError(() => ({ detail: 'Falhou', status: 500 })), of([notified()])), inputs);
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Falhou');
    press(fixture, button(root, 'Tentar novamente'));
    expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
    expect(root.querySelector('h2')?.textContent).toBe('Reserva de Maria Silva');
  });

  it('sem o filtro de cliente na URL consulta todas as reservas', () => {
    const { service } = create(CounterReservationAttendComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified()])), { id: '31' });
    expect(service.listPurchaseReservations).toHaveBeenCalledOnceWith({ clientId: null });
  });
});

describe('Reservas de compra: cancelamento, prazo e expiração (Issue #150)', () => {
  const dialog = (root: HTMLElement) => root.querySelector('dialog');
  const confirmButton = (root: HTMLElement) => dialog(root)!.querySelector('.confirm__submit') as HTMLButtonElement;

  it('cancela a reserva somente após confirmar, bloqueia o envio duplo e só mostra sucesso após o 2xx', () => {
    const response = new Subject<{ id: number }>();
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([waiting()]));
      s.cancelReservation.and.returnValue(response);
    });
    press(fixture, button(root, 'Cancelar reserva de Ana Santos'));
    expect(service.cancelReservation).not.toHaveBeenCalled();
    expect(dialog(root)!.textContent).toContain('Cancelar reserva?');
    press(fixture, confirmButton(root));
    press(fixture, confirmButton(root));
    expect(service.cancelReservation).toHaveBeenCalledOnceWith(32);
    expect(snackbarMessage()).not.toContain('cancelada');
    response.next({ id: 32 });
    response.complete();
    fixture.detectChanges();
    expect(snackbarMessage()).toContain('Reserva de Ana Santos para “Dom Casmurro” cancelada.');
    expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
  });

  it('cancelar a reserva destinada avisa que o exemplar será liberado', () => {
    const { fixture, root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified()])));
    press(fixture, button(root, 'Cancelar reserva de Maria Silva'));
    expect(dialog(root)!.textContent).toContain('O exemplar destinado será liberado');
  });

  it('mostra a recusa de estado final sem sucesso e recarrega', () => {
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([waiting()]));
      s.cancelReservation.and.returnValue(throwError(() => ({ detail: 'Esta reserva já foi encerrada e não pode ser cancelada. Atualize a lista.', code: 'reservation_not_cancellable', status: 409 })));
    });
    press(fixture, button(root, 'Cancelar reserva de Ana Santos'));
    press(fixture, confirmButton(root));
    expect(snackbarMessage()).toContain('já foi encerrada');
    expect(snackbarVariant()).toBe('warning');
    expect(service.listPurchaseReservations).toHaveBeenCalledTimes(2);
  });

  it('a inelegível à frente mantém a posição e a elegível seguinte recebe o botão de destinar', () => {
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([
      waiting({ id: 30, can_allocate: false, allocation_blocked_reason: 'CLIENT_INELIGIBLE', client: client({ id: 8, name: 'Bia Lima', eligible: false, is_penalized: true }) }),
      waiting({ id: 33, queue_position: 2 }),
    ])));
    expect(root.textContent).toContain('1ª · Bia Lima');
    expect(root.textContent).not.toContain('Destinar exemplar a Bia Lima');
    expect(root.textContent).toContain('Destinar exemplar a Ana Santos');
  });

  it('oferece liberar exemplares vencidos somente quando há reserva vencida e mostra a quantidade após o 2xx', () => {
    const { fixture, root, service } = create(CounterReservationsComponent, (s) => {
      s.listPurchaseReservations.and.returnValue(of([notified({ expired: true, expires_at: '2026-09-01T12:00:00Z' })]));
      s.expireDueReservations.and.returnValue(of({ expired: 1 }));
    });
    expect(root.textContent).toContain('Há reservas com prazo de retirada vencido');
    press(fixture, button(root, 'Liberar exemplares vencidos'));
    expect(service.expireDueReservations).not.toHaveBeenCalled();
    press(fixture, confirmButton(root));
    expect(service.expireDueReservations).toHaveBeenCalledTimes(1);
    expect(snackbarMessage()).toContain('1 reserva vencida foi encerrada.');
  });

  it('sem reserva vencida não oferece a liberação', () => {
    const { root } = create(CounterReservationsComponent, (s) => s.listPurchaseReservations.and.returnValue(of([notified({ expires_at: '2099-01-01T12:00:00Z' })])));
    expect(root.textContent).not.toContain('Liberar exemplares vencidos');
    expect(root.textContent).toContain('Retirar até 01/01/2099');
  });
});
