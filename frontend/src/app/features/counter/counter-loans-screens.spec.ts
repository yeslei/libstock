import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { receiptGet, receiptStub } from '../receipts/receipt-testing.spec';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../app.routes';
import { CounterActiveLoansComponent } from './counter-active-loans.component';
import { CounterContext } from './counter-context.service';
import { CounterReturnsComponent } from './counter-returns.component';
import { CounterService, StaffClient, StaffLoan } from './counter.service';

const client: StaffClient = {
  id: 3, name: 'Ana Souza', email: 'ana@x.dev', is_active: true, is_penalized: false, has_overdue_loan: false, eligible: true,
};
const book = { id: 10, title: 'Dom Casmurro', author: 'Machado de Assis', is_active: true };

const loan = (over: Partial<StaffLoan> = {}): StaffLoan => ({
  id: 21, client, book, copy_id: 91, copy_barcode: 'D-001', loan_date: '2026-09-01T12:00:00Z',
  due_date: '2026-10-01T12:00:00Z', status: 'OVERDUE', days_late: 2, ...over,
});

function setup<T>(component: new () => T, configure: (service: jasmine.SpyObj<CounterService>) => void) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['listLoans', 'confirmReturn']);
  configure(service);
  TestBed.configureTestingModule({
    imports: [component],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }, receiptStub()],
  });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

function click(fixture: ComponentFixture<unknown>, element: HTMLElement) {
  element.click();
  fixture.detectChanges();
}

function button(root: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`Botão não encontrado: ${label}`);
  return found as HTMLButtonElement;
}

function submitSearch(fixture: ComponentFixture<unknown>, root: HTMLElement, term: string) {
  const input = root.querySelector('input[type="search"]') as HTMLInputElement;
  input.value = term;
  input.dispatchEvent(new Event('input'));
  root.querySelector('form')!.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

describe('Balcão: empréstimos ativos', () => {
  it('lista os empréstimos em tabela somente leitura, com colunas, contadores e rodapé da referência', () => {
    const { root, service } = setup(CounterActiveLoansComponent, (s) =>
      s.listLoans.and.returnValue(of([
        loan({ id: 1, status: 'ACTIVE', days_late: 0, due_date: '2026-10-20T12:00:00Z' }),
        loan({ id: 2, status: 'ACTIVE', days_late: 0 }),
        loan({ id: 3 }),
      ])));
    expect(service.listLoans).toHaveBeenCalledWith({ q: '', clientId: undefined });
    expect(root.querySelector('h1')?.textContent).toBe('Empréstimos ativos');
    expect(Array.from(root.querySelectorAll('th')).map((th) => th.textContent?.trim())).toEqual([
      'Cliente', 'Obra / exemplar', 'Retirada', 'Devolução', 'Status']);
    const rows = root.querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);
    expect(rows[0].textContent).toContain('Ana Souza');
    expect(rows[0].textContent).toContain('Dom Casmurro · D-001');
    expect(rows[0].textContent).toContain('01/09/2026');
    expect(rows[0].textContent).toContain('20/10/2026');
    expect(rows[0].textContent).toContain('Ativo');
    expect(rows[2].classList).toContain('row--danger');
    expect(rows[2].textContent).toContain('Atrasado');
    expect(rows[2].textContent).toContain('há 2 dia(s)');
    expect(root.querySelector('.counter')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('2 ativos • 1 atrasados');
    expect(root.textContent).toContain('Atraso gera pendência do cliente até a devolução ser registrada.');
    expect(root.querySelector('tbody button')).toBeNull();
    expect(root.querySelector('a.page__back')?.getAttribute('href')).toBe('/balcao/emprestimos');
  });

  it('mostra carregamento e depois o estado vazio, sem tabela', () => {
    const pending = new Subject<StaffLoan[]>();
    const { fixture, root } = setup(CounterActiveLoansComponent, (s) => s.listLoans.and.returnValue(pending));
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Carregando');
    pending.next([]);
    fixture.detectChanges();
    expect(root.textContent).toContain('Nenhum empréstimo ativo encontrado.');
    expect(root.querySelector('table')).toBeNull();
    expect(root.querySelector('.counter')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('0 ativos • 0 atrasados');
  });

  it('diferencia erro de lista vazia e recarrega ao tentar de novo', () => {
    const { fixture, root, service } = setup(CounterActiveLoansComponent, (s) =>
      s.listLoans.and.returnValue(throwError(() => ({ detail: 'Falha ao consultar.' }))));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Falha ao consultar.');
    expect(root.textContent).not.toContain('Nenhum empréstimo ativo encontrado.');
    service.listLoans.and.returnValue(of([loan()]));
    click(fixture, button(root, 'Tentar novamente'));
    expect(root.querySelectorAll('tbody tr').length).toBe(1);
  });

  it('busca pelo termo informado', () => {
    const { fixture, root, service } = setup(CounterActiveLoansComponent, (s) => s.listLoans.and.returnValue(of([])));
    submitSearch(fixture, root, ' Dom ');
    expect(service.listLoans.calls.mostRecent().args[0]).toEqual({ q: ' Dom ', clientId: undefined });
  });

  it('aplica o filtro de cliente do contexto e permite removê-lo', () => {
    const { fixture, root, service } = setup(CounterActiveLoansComponent, (s) => s.listLoans.and.returnValue(of([])));
    TestBed.inject(CounterContext).client.set(client);
    fixture.componentInstance['reload']();
    fixture.detectChanges();
    expect(service.listLoans.calls.mostRecent().args[0]).toEqual({ q: '', clientId: 3 });
    expect(root.querySelector('.chip')?.textContent).toContain('Ana Souza');
    click(fixture, button(root, 'Remover filtro'));
    expect(TestBed.inject(CounterContext).client()).toBeNull();
    expect(service.listLoans.calls.mostRecent().args[0]).toEqual({ q: '', clientId: undefined });
  });

  it('avisa que os contadores consideram só os listados quando o limite é atingido', () => {
    const many = Array.from({ length: 50 }, (_, i) => loan({ id: i + 1, status: 'ACTIVE', days_late: 0 }));
    const { root } = setup(CounterActiveLoansComponent, (s) => s.listLoans.and.returnValue(of(many)));
    expect(root.querySelector('.note')?.textContent).toContain('Mostrando os primeiros 50');
  });
});

describe('Balcão: registrar devolução', () => {
  const dialog = (root: HTMLElement) => root.querySelector('dialog');
  const submitButton = (root: HTMLElement) => dialog(root)!.querySelector('.confirm__submit') as HTMLButtonElement;

  it('não consulta antes da busca e exige o código ou o ISBN', () => {
    const { fixture, root, service } = setup(CounterReturnsComponent, () => undefined);
    expect(root.querySelector('h1')?.textContent).toBe('Registrar devolução');
    expect(root.querySelector('input')?.getAttribute('placeholder')).toBe('Código do exemplar ou ISBN');
    expect(service.listLoans).not.toHaveBeenCalled();
    submitSearch(fixture, root, '   ');
    expect(service.listLoans).not.toHaveBeenCalled();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Informe o código do exemplar ou o ISBN.');
  });

  it('busca por código ou ISBN e mostra obra, exemplar, cliente e devolução prevista', () => {
    const { fixture, root, service } = setup(CounterReturnsComponent, (s) => s.listLoans.and.returnValue(of([loan()])));
    submitSearch(fixture, root, ' 9788535902778 ');
    expect(service.listLoans).toHaveBeenCalledOnceWith({ q: '9788535902778' });
    const card = root.querySelector('article')!;
    expect(card.textContent).toContain('Dom Casmurro');
    expect(card.textContent).toContain('Exemplar D-001');
    expect(card.textContent).toContain('Cliente: Ana Souza');
    expect(card.textContent).toContain('Devolução prevista: 01/10/2026');
    expect(card.textContent).toContain('Atrasado há 2 dia(s)');
  });

  it('mostra carregamento, vazio e erro de forma distinta', () => {
    const pending = new Subject<StaffLoan[]>();
    const { fixture, root, service } = setup(CounterReturnsComponent, (s) => s.listLoans.and.returnValue(pending));
    submitSearch(fixture, root, 'X-1');
    expect(root.textContent).toContain('Buscando empréstimo');
    pending.next([]);
    fixture.detectChanges();
    expect(root.querySelector('.empty')?.textContent).toContain('Nenhum empréstimo ativo encontrado para “X-1”');
    service.listLoans.and.returnValue(throwError(() => ({ detail: 'Falha ao consultar.' })));
    submitSearch(fixture, root, 'X-2');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Falha ao consultar.');
    expect(root.querySelector('.empty')).toBeNull();
  });

  it('pede confirmação antes do POST e cancelar não envia', () => {
    const { fixture, root, service } = setup(CounterReturnsComponent, (s) => s.listLoans.and.returnValue(of([loan()])));
    submitSearch(fixture, root, 'D-001');
    click(fixture, button(root, 'Confirmar devolução'));
    expect(dialog(root)?.textContent).toContain('Confirmar devolução?');
    expect(dialog(root)?.textContent).toContain('Empréstimo em atraso há 2 dia(s).');
    click(fixture, button(root, 'Cancelar'));
    expect(dialog(root)).toBeNull();
    expect(service.confirmReturn).not.toHaveBeenCalled();
  });

  it('bloqueia envio duplicado, só anuncia sucesso após a resposta e recarrega a busca', () => {
    const response = new Subject<{ id: number }>();
    const { fixture, root, service } = setup(CounterReturnsComponent, (s) => {
      s.listLoans.and.returnValue(of([loan()]));
      s.confirmReturn.and.returnValue(response);
    });
    submitSearch(fixture, root, 'D-001');
    click(fixture, button(root, 'Confirmar devolução'));
    const submit = submitButton(root);
    click(fixture, submit);
    click(fixture, submit);
    expect(service.confirmReturn).toHaveBeenCalledOnceWith(21);
    expect(submit.disabled).toBeTrue();
    expect(root.textContent).not.toContain('Devolução confirmada:');
    service.listLoans.and.returnValue(of([]));
    response.next({ id: 21 });
    response.complete();
    fixture.detectChanges();
    expect(dialog(root)).toBeNull();
    expect(snackbarMessage()).toContain('Devolução confirmada: exemplar D-001 de “Dom Casmurro”.');
    expect(receiptGet()).toHaveBeenCalledOnceWith('return', 21);
    expect(root.querySelector('app-receipt')).not.toBeNull();
    expect(service.listLoans).toHaveBeenCalledTimes(2);
    expect(root.querySelector('.empty')).not.toBeNull();
  });

  it('mostra o erro de domínio sem sucesso e recarrega a busca', () => {
    const { fixture, root, service } = setup(CounterReturnsComponent, (s) => {
      s.listLoans.and.returnValue(of([loan({ status: 'ACTIVE', days_late: 0 })]));
      s.confirmReturn.and.returnValue(throwError(() => ({ detail: 'Empréstimo já encerrado.', code: 'loan_already_closed' })));
    });
    submitSearch(fixture, root, 'D-001');
    click(fixture, button(root, 'Confirmar devolução'));
    expect(dialog(root)?.textContent).toContain('Empréstimo dentro do prazo.');
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('Empréstimo já encerrado.');
    expect(root.textContent).not.toContain('Devolução confirmada:');
    expect(service.listLoans).toHaveBeenCalledTimes(2);
  });
});

describe('Rotas dos empréstimos ativos e da devolução', () => {
  const children = routes.find((r) => r.path === 'balcao')?.children ?? [];

  it('mapeia as duas telas para componentes próprios', async () => {
    const active = await children.find((r) => r.path === 'emprestimos/ativos')!.loadComponent!();
    const returns = await children.find((r) => r.path === 'devolucoes')!.loadComponent!();
    expect(active).toBe(CounterActiveLoansComponent);
    expect(returns).toBe(CounterReturnsComponent);
  });
});
