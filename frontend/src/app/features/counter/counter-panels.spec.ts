import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { Provider, Type } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../app.routes';
import { receiptGet, receiptStub } from '../receipts/receipt-testing.spec';
import { CounterService, StaffClient, StaffLoan, StaffLoanRequest } from './counter.service';
import { ClientsPanelComponent } from './clients-panel.component';
import { businessToday } from './business-date';
import { CounterContext } from './counter-context.service';
import { CounterClientsPageComponent } from './counter-pages';
import { PickupsPanelComponent } from './pickups-panel.component';

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

type Spies = {
  [K in keyof CounterService]: jasmine.Spy;
};

function setup<T>(component: Type<T>, configure: (service: Spies) => void = () => undefined, extra: Provider[] = []) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', [
    'searchClients', 'getClientPendencies', 'listLoanRequests', 'confirmPickup', 'listLoans', 'confirmReturn',
    'listPurchaseReservations', 'allocatePurchase', 'confirmSale',
  ]) as unknown as Spies;
  service.searchClients.and.returnValue(of([]));
  configure(service);
  TestBed.configureTestingModule({ imports: [component], providers: [provideRouter([]), { provide: CounterService, useValue: service }, receiptStub(), ...extra] });
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
    expect(snackbarMessage()).toContain('Retirada confirmada. Empréstimo #77');
    expect(receiptGet()).toHaveBeenCalledOnceWith('loan', 77);
    expect(root.querySelector('app-receipt')).not.toBeNull();
    expect(service.listLoanRequests).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain('Nenhuma solicitação de empréstimo pendente.');
  });

  it('falha 5xx na retirada mostra "Não foi possível salvar", sem snackbar, e só consulta de novo ao atualizar', () => {
    const { fixture, root, service } = setup(PickupsPanelComponent, (s) => {
      s.listLoanRequests.and.returnValue(of([loanRequest()]));
      s.confirmPickup.and.returnValue(throwError(() => ({ status: 500, detail: 'Tivemos um problema no servidor.' })));
    });
    const select = root.querySelector('select') as HTMLSelectElement;
    select.value = '91'; select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    click(fixture, button(root, 'Confirmar retirada'));
    click(fixture, dialog(root)!.querySelector('.confirm__submit') as HTMLElement);
    expect(root.querySelector('app-save-failure')?.textContent).toContain('Não foi possível salvar');
    expect(snackbarMessage()).toBe('');
    expect(service.confirmPickup).toHaveBeenCalledTimes(1);
    expect(service.listLoanRequests).toHaveBeenCalledTimes(2);
    click(fixture, button(root, 'Atualizar consulta'));
    expect(service.listLoanRequests).toHaveBeenCalledTimes(3);
    expect(service.confirmPickup).toHaveBeenCalledTimes(1);
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
    expect(snackbarMessage()).toContain('já foi confirmada');
    expect(snackbarVariant()).toBe('warning');
    expect(snackbarMessage()).not.toContain('Retirada confirmada.');
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

describe('Balcão: controle de pendências', () => {
  function search(fixture: ComponentFixture<unknown>, root: HTMLElement, term: string) {
    const input = root.querySelector('#client-q') as HTMLInputElement;
    input.value = term; input.dispatchEvent(new Event('input'));
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('abre listando os clientes ativos, sem consultar pendências nem prometer CPF', () => {
    const { root, service } = setup(ClientsPanelComponent, (s) =>
      s.searchClients.and.returnValue(of([client(), client({ id: 4, name: 'Bia' })])));
    expect(root.querySelector('h1')?.textContent).toContain('Controle de pendências');
    expect(service.searchClients).toHaveBeenCalledOnceWith(undefined);
    expect(root.querySelectorAll('.pick').length).toBe(2);
    expect(root.textContent).toContain('2 clientes ativos');
    expect(root.textContent).toContain('Escolha um cliente da lista');
    expect(service.getClientPendencies).not.toHaveBeenCalled();
    expect((root.querySelector('#client-q') as HTMLInputElement).placeholder).toBe('Filtrar por nome ou e-mail');
    expect(root.textContent).not.toContain('CPF');
  });

  it('com um único cliente na lista padrão, lista sem abrir a consulta; o filtro por termo abre', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent, (s) => {
      s.searchClients.and.returnValue(of([client()]));
      s.getClientPendencies.and.returnValue(of({ client: client(), overdue_loans: [] }));
    });
    expect(root.querySelectorAll('.pick').length).toBe(1);
    expect(service.getClientPendencies).not.toHaveBeenCalled();
    search(fixture, root, '');
    expect(service.searchClients.calls.mostRecent().args).toEqual([undefined]);
    expect(service.getClientPendencies).not.toHaveBeenCalled();
    search(fixture, root, 'ana');
    expect(service.getClientPendencies).toHaveBeenCalledOnceWith(3);
  });

  it('não consulta com termo curto e orienta o funcionário', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent);
    search(fixture, root, ' a ');
    expect(service.searchClients).toHaveBeenCalledTimes(1); // só a lista inicial
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('ao menos 2 caracteres');
  });

  it('mostra carregamento enquanto busca', () => {
    const pending = new Subject<StaffClient[]>();
    const { fixture, root } = setup(ClientsPanelComponent, (s) => s.searchClients.and.returnValue(pending));
    expect(root.textContent).toContain('Carregando clientes');
    search(fixture, root, 'ana');
    expect(root.textContent).toContain('Carregando clientes');
  });

  it('cliente sem pendência: consulta o único resultado e mostra a situação', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent, (s) => {
      s.searchClients.and.returnValue(of([client()]));
      s.getClientPendencies.and.returnValue(of({ client: client(), overdue_loans: [] }));
    });
    search(fixture, root, 'ana');
    expect(service.searchClients.calls.mostRecent().args).toEqual(['ana']);
    expect(service.getClientPendencies).toHaveBeenCalledOnceWith(3);
    expect(root.textContent).toContain('Ana Souza');
    expect(root.textContent).toContain('Sem pendência');
    expect(root.textContent).not.toContain('Pendência ativa');
  });

  it('pendência ativa: exemplar, obra, vencimento e dias de atraso', () => {
    const { fixture, root } = setup(ClientsPanelComponent, (s) => {
      s.searchClients.and.returnValue(of([client(), client({ id: 4, name: 'Bia', eligible: false, has_overdue_loan: true })]));
      s.getClientPendencies.and.returnValue(of({ client: client({ id: 4, name: 'Bia', is_penalized: true, eligible: false }),
        overdue_loans: [loan({ id: 1, days_late: 3, copy_barcode: '00127', due_date: '2026-09-15T12:00:00Z' })] }));
    });
    search(fixture, root, 'an');
    expect(root.querySelectorAll('.pick').length).toBe(2);
    click(fixture, root.querySelectorAll<HTMLButtonElement>('.pick')[1]);
    expect(root.textContent).toContain('Pendência ativa');
    expect(root.textContent).toContain('Empréstimo em atraso');
    expect(root.textContent).toContain('Dom Casmurro');
    expect(root.textContent).toContain('Exemplar #00127');
    expect(root.textContent).toContain('vencimento 15/09/2026');
    expect(root.textContent).toContain('3 dia(s) de atraso');
    expect(root.textContent).toContain('Pendência = empréstimo não devolvido após a data prevista');
    expect(root.textContent).toContain('penalizado');
  });

  it('avisa quando a lista de clientes atinge o limite', () => {
    const many = Array.from({ length: 20 }, (_, i) => client({ id: i + 1 }));
    const { fixture, root } = setup(ClientsPanelComponent, (s) => s.searchClients.and.returnValue(of(many)));
    expect(root.textContent).toContain('Mostrando os primeiros 20 resultados');
    search(fixture, root, 'an');
    expect(root.textContent).toContain('Mostrando os primeiros 20 resultados');
  });

  it('mostra vazio e erro de busca de forma distinta', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent, (s) => s.searchClients.and.returnValue(of([])));
    expect(root.textContent).toContain('Nenhum cliente ativo cadastrado.');
    search(fixture, root, 'zz');
    expect(root.textContent).toContain('Nenhum cliente encontrado');
    service.searchClients.and.returnValue(throwError(() => ({ detail: 'Permissão insuficiente.' }) ));
    search(fixture, root, 'zzz');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Permissão insuficiente.');
    expect(button(root, 'Tentar novamente')).toBeTruthy();
  });

  it('mostra erro da consulta de pendências com nova tentativa', () => {
    const { fixture, root, service } = setup(ClientsPanelComponent, (s) => {
      s.searchClients.and.returnValue(of([client()]));
      s.getClientPendencies.and.returnValue(throwError(() => ({})));
    });
    search(fixture, root, 'ana');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível consultar as pendências');
    service.getClientPendencies.and.returnValue(of({ client: client(), overdue_loans: [] }));
    click(fixture, button(root, 'Tentar novamente'));
    expect(root.textContent).toContain('Sem pendência');
  });

  it('abre a tela escolhida guardando o cliente como filtro', () => {
    const router = jasmine.createSpyObj<Router>('Router', ['navigateByUrl']);
    const { fixture, root } = setup(CounterClientsPageComponent, (s) => {
      s.searchClients.and.returnValue(of([client()]));
      s.getClientPendencies.and.returnValue(of({ client: client(), overdue_loans: [] }));
    }, [{ provide: Router, useValue: router }, { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({}) } } }]);
    search(fixture, root, 'ana');
    click(fixture, button(root, 'Empréstimos ativos'));
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

  it('é protegida por autenticação e aberta a SELLER, STOCK_KEEPER e ADMINISTRATOR (telas de atendimento restritas por rota)', () => {
    expect(counter?.canActivate?.length).toBe(2);
    expect(counter?.data?.['roles']).toEqual(['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR']);
  });

  it('restringe a SELLER e ADMINISTRATOR toda rota filha que não é de acervo (Issue #169)', () => {
    const children = (counter?.children ?? []).filter((r) => r.loadComponent);
    for (const route of children) {
      const stockKeeperAllowed = route.path === 'acervo' || route.path!.startsWith('acervo/');
      if (stockKeeperAllowed) {
        expect(route.data?.['roles']).withContext(route.path ?? '').toBeUndefined();
      } else {
        expect(route.canActivate?.length).withContext(route.path ?? '').toBe(1);
        expect(route.data?.['roles']).withContext(route.path ?? '').toEqual(['SELLER', 'ADMINISTRATOR']);
        expect(route.data?.['deniedRedirect']).withContext(route.path ?? '').toBe('/balcao/acervo');
      }
    }
    expect(children.map((r) => r.path)).toEqual(jasmine.arrayContaining(['painel', 'clientes', 'vendas', 'reservas/:id']));
  });

  it('declara as telas do funcionário como rotas filhas do layout', () => {
    const paths = counter?.children?.map((r) => r.path);
    expect(paths).toEqual(jasmine.arrayContaining(['clientes', 'emprestimos/solicitacoes', 'emprestimos/ativos', 'devolucoes', 'vendas']));
  });
});
