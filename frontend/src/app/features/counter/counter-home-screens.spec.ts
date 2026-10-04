import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { businessToday } from './business-date';
import { CounterDashboardComponent } from './counter-dashboard.component';
import { CounterLoansHomeComponent } from './counter-loans-home.component';
import { CounterService, StaffDashboard, StaffLoan, StaffLoanRequest } from './counter.service';

const dashboard: StaffDashboard = { active_loans: 32, returns_today: 8, waiting_reservations: 4, pendencies: 3 };
const client = { id: 3, name: 'Ana', email: 'ana@x.dev', is_active: true, is_penalized: false, has_overdue_loan: false, eligible: true };
const book = { id: 10, title: 'Dom Casmurro', author: 'Machado', is_active: true };

function setup<T>(component: new () => T, configure: (service: jasmine.SpyObj<CounterService>) => void) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['getDashboard', 'listLoanRequests', 'listLoans']);
  configure(service);
  TestBed.configureTestingModule({
    imports: [component],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }],
  });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

describe('Balcão: painel', () => {
  it('mostra os quatro cartões de acesso, na ordem e com os textos do Figma', () => {
    const { root } = setup(CounterDashboardComponent, (s) => s.getDashboard.and.returnValue(of(dashboard)));
    expect(root.querySelector('h1')?.textContent).toBe('Painel');
    expect(root.textContent).toContain('Acesso rápido às operações da biblioteca.');
    const cards = Array.from(root.querySelectorAll('a.card--access'));
    expect(cards.map((c) => c.querySelector('.card__title')?.textContent)).toEqual([
      'Consultar acervo', 'Registrar devolução', 'Vendas', 'Empréstimo']);
    expect(cards.map((c) => c.getAttribute('href'))).toEqual(['/balcao/acervo', '/balcao/devolucoes', '/balcao/vendas', '/balcao/emprestimos/novo']);
    expect(cards[0].textContent).toContain('Buscar obras e disponibilidade');
    expect(cards[0].textContent).toContain('Acessar');
  });

  it('exibe os indicadores vindos do backend', () => {
    const { root } = setup(CounterDashboardComponent, (s) => s.getDashboard.and.returnValue(of(dashboard)));
    const text = (selector: string) => Array.from(root.querySelectorAll(selector)).map((el) => el.textContent?.trim());
    expect(text('.card--indicator .card__value')).toEqual(['32', '8', '4', '3']);
    expect(text('.card--indicator .card__label')).toEqual(['Empréstimos ativos', 'Devoluções hoje', 'Reservas aguardando', 'Pendências']);
  });

  it('indica carregamento sem inventar números e depois mostra os valores', () => {
    const pending = new Subject<StaffDashboard>();
    const { fixture, root } = setup(CounterDashboardComponent, (s) => s.getDashboard.and.returnValue(pending));
    expect(root.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(root.querySelector('.card__value')?.textContent).toBe('—');
    pending.next(dashboard);
    fixture.detectChanges();
    expect(root.querySelector('.card__value')?.textContent).toBe('32');
  });

  it('mostra o erro de domínio e permite tentar de novo sem exibir números', () => {
    const { fixture, root, service } = setup(CounterDashboardComponent, (s) =>
      s.getDashboard.and.returnValue(throwError(() => ({ detail: 'Cadastro de funcionário ativo necessário.' }))));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Cadastro de funcionário ativo necessário.');
    expect(root.querySelector('.card__value')?.textContent).toBe('—');
    service.getDashboard.and.returnValue(of(dashboard));
    (Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Tentar novamente') as HTMLElement).click();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')).toBeNull();
    expect(root.querySelector('.card__value')?.textContent).toBe('32');
  });
});

describe('Balcão: empréstimos / início', () => {
  const request = (pickup_date: string): StaffLoanRequest => ({
    id: 1, client, book, pickup_date, due_date: '2026-12-01', created_at: '2026-10-01T12:00:00Z', eligible_copies: [],
  });
  const loan = (status: 'ACTIVE' | 'OVERDUE'): StaffLoan => ({
    id: 1, client, book, copy_id: 1, copy_barcode: 'C1', loan_date: '2026-09-01T12:00:00Z',
    due_date: '2026-10-01T12:00:00Z', status, days_late: status === 'OVERDUE' ? 2 : 0,
  });

  it('mostra os três cartões, o de novo empréstimo sem contagem, com contagens calculadas a partir do backend', () => {
    const today = businessToday();
    const { root } = setup(CounterLoansHomeComponent, (s) => {
      s.getDashboard.and.returnValue(of(dashboard));
      s.listLoanRequests.and.returnValue(of([request(today), request(today), request('2000-01-01')]));
      s.listLoans.and.returnValue(of([loan('OVERDUE'), loan('ACTIVE')]));
    });
    expect(root.querySelector('h1')?.textContent).toBe('Empréstimos');
    expect(root.textContent).toContain('Escolha o que você precisa consultar ou atender.');
    const badges = Array.from(root.querySelectorAll('.card__badge')).map((b) => b.textContent?.trim());
    expect(badges).toEqual(['2 aguardando hoje', '32 ativos · 1 atrasados']);
    const links = Array.from(root.querySelectorAll('a.card__action'));
    expect(links.map((a) => a.textContent?.trim())).toEqual(['Ver solicitações →', 'Ver empréstimos →', 'Novo empréstimo →']);
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/balcao/emprestimos/solicitacoes', '/balcao/emprestimos/ativos', '/balcao/emprestimos/novo']);
  });

  it('não afirma quantos estão atrasados quando a lista de empréstimos foi truncada', () => {
    const many = Array.from({ length: 50 }, () => loan('ACTIVE'));
    const { root } = setup(CounterLoansHomeComponent, (s) => {
      s.getDashboard.and.returnValue(of(dashboard));
      s.listLoanRequests.and.returnValue(of([]));
      s.listLoans.and.returnValue(of(many));
    });
    const badges = Array.from(root.querySelectorAll('.card__badge')).map((b) => b.textContent?.trim());
    expect(badges).toEqual(['0 aguardando hoje', '32 ativos']);
  });

  it('mostra erro com nova tentativa quando alguma consulta falha', () => {
    const { fixture, root, service } = setup(CounterLoansHomeComponent, (s) => {
      s.getDashboard.and.returnValue(throwError(() => ({ detail: 'Falha ao consultar.' })));
      s.listLoanRequests.and.returnValue(of([]));
      s.listLoans.and.returnValue(of([]));
    });
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Falha ao consultar.');
    expect(Array.from(root.querySelectorAll('.card__badge')).map((b) => b.textContent?.trim())).toEqual(['Indisponível', 'Indisponível']);
    service.getDashboard.and.returnValue(of(dashboard));
    (Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Tentar novamente') as HTMLElement).click();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')).toBeNull();
  });
});
