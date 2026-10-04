import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, catchError, forkJoin, map, of, startWith, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { businessToday } from './business-date';
import { CounterService, LIST_LIMIT } from './counter.service';
import { errorMessage } from './desk-panel';

export interface LoansSummary {
  readonly waitingToday: number;
  readonly active: number;
  /** Nulo quando a lista de empréstimos foi truncada pelo limite e a contagem de atrasados não é confiável. */
  readonly overdue: number | null;
}

/** Frame "Funcionário / Empréstimos / Início" (Figma 20:2). Contagens vindas do backend, sem valores fixos. */
@Component({
  selector: 'app-counter-loans-home',
  standalone: true,
  imports: [RouterLink, AlertComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-loans-home.component.html',
  styleUrl: './counter-loans-home.component.scss',
})
export class CounterLoansHomeComponent implements OnInit {
  private readonly service = inject(CounterService);
  private readonly loads = new Subject<void>();

  protected readonly state = signal<LoadState<LoansSummary>>({ status: 'loading' });

  constructor() {
    this.loads
      .pipe(
        switchMap(() =>
          forkJoin({
            dashboard: this.service.getDashboard(),
            requests: this.service.listLoanRequests(),
            loans: this.service.listLoans(),
          }).pipe(
            map(({ dashboard, requests, loans }): LoadState<LoansSummary> => {
              const today = businessToday();
              return {
                status: 'loaded',
                data: {
                  waitingToday: requests.filter((request) => request.pickup_date === today).length,
                  active: dashboard.active_loans,
                  overdue: loans.length < LIST_LIMIT ? loans.filter((loan) => loan.status === 'OVERDUE').length : null,
                },
              };
            }),
            startWith<LoadState<LoansSummary>>({ status: 'loading' }),
            catchError((error) =>
              of<LoadState<LoansSummary>>({
                status: 'error',
                message: errorMessage(error, 'Não foi possível carregar o resumo de empréstimos.'),
              }),
            ),
          ),
        ),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((state) => this.state.set(state));
  }

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loads.next();
  }

  protected waitingLabel(summary: LoansSummary): string {
    return `${summary.waitingToday} aguardando hoje`;
  }

  protected activeLabel(summary: LoansSummary): string {
    const active = `${summary.active} ativos`;
    return summary.overdue === null ? active : `${active} · ${summary.overdue} atrasados`;
  }
}
