import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { AuthService } from '../../core/services/auth.service';
import { businessToday } from './business-date';
import { CounterDashboardComponent } from './counter-dashboard.component';
import { CounterLoansHomeComponent } from './counter-loans-home.component';
import { CounterService, StaffDashboard, StaffLoan, StaffLoanRequest } from './counter.service';

const dashboard: StaffDashboard = { active_loans: 32, returns_today: 8, waiting_reservations: 4, pendencies: 3 };
const client = { id: 3, name: 'Ana', email: 'ana@x.dev', is_active: true, is_penalized: false, has_overdue_loan: false, eligible: true };
const book = { id: 10, title: 'Dom Casmurro', author: 'Machado', is_active: true };

function setup<T>(component: new () => T, configure: (service: jasmine.SpyObj<CounterService>) => void) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['getDashboard', 'getDashboardOverview', 'listLoanRequests', 'listLoans']);
  service.getDashboardOverview.and.returnValue(of({ loans_today: 2, week: [], categories: [], popular: [], recent_loans: [], recent_returns: [] }));
  configure(service);
  TestBed.configureTestingModule({
    imports: [component],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }, { provide: AuthService, useValue: { currentUser: { name: 'Vendedor', role_codes: ['SELLER'] }, logout: () => of(undefined) } }],
  });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

describe('Balcão: painel', () => {
  it('prioriza as ações de circulação no hero e mantém a estrutura editorial', () => {
    const { root } = setup(CounterDashboardComponent, (s) => s.getDashboard.and.returnValue(of(dashboard)));
    expect(root.querySelector('.global-search')).toBeNull();
    expect(root.querySelector('.page-heading')).toBeNull();
    const links = Array.from(root.querySelectorAll('.hero__actions a'));
    expect(links.map(a => a.getAttribute('href'))).toEqual(['/balcao/emprestimos/novo', '/balcao/devolucoes']);
    expect(root.querySelector('app-weekly-movement')).not.toBeNull();
    expect(root.querySelector('app-category-chart')).not.toBeNull();
    expect(root.textContent).not.toContain('Precisa da sua atenção');
    expect(root.textContent).toContain('Ainda não há empréstimos registrados');
  });

  it('exibe os indicadores vindos do backend', () => {
    const { root } = setup(CounterDashboardComponent, (s) => s.getDashboard.and.returnValue(of(dashboard)));
    const text = (selector: string) => Array.from(root.querySelectorAll(selector)).map((el) => el.textContent?.trim());
    expect(text('app-stat-card strong')).toEqual(['2', '8', '4', '3']);
    expect(text('app-stat-card .label')).toEqual(['Empréstimos do dia', 'Devoluções do dia', 'Reservas aguardando', 'Pendências']);
  });

  it('indica carregamento sem inventar números e depois mostra os valores', () => {
    const pending = new Subject<StaffDashboard>();
    const { fixture, root } = setup(CounterDashboardComponent, (s) => s.getDashboard.and.returnValue(pending));
    expect(root.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(root.querySelector('app-stat-card strong')?.textContent).toBe('—');
    pending.next(dashboard); pending.complete();
    fixture.detectChanges();
    expect(root.querySelector('app-stat-card strong')?.textContent).toBe('2');
  });

  it('mostra o erro de domínio e permite tentar de novo sem exibir números', () => {
    const { fixture, root, service } = setup(CounterDashboardComponent, (s) =>
      s.getDashboard.and.returnValue(throwError(() => ({ detail: 'Cadastro de funcionário ativo necessário.' }))));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Cadastro de funcionário ativo necessário.');
    expect(root.querySelector('app-stat-card strong')?.textContent).toBe('—');
    service.getDashboard.and.returnValue(of(dashboard));
    (Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Tentar novamente') as HTMLElement).click();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')).toBeNull();
    expect(root.querySelector('app-stat-card strong')?.textContent).toBe('2');
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
