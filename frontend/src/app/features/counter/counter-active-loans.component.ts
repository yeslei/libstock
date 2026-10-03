import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { CounterContext } from './counter-context.service';
import { CounterService, LIST_LIMIT, StaffLoan } from './counter.service';
import { toLoadState } from './desk-flow';

/** Frame "Funcionário / Empréstimos / Ativos": tabela somente leitura; atraso decidido pelo backend (regra V2). */
@Component({
  selector: 'app-counter-active-loans',
  standalone: true,
  imports: [DatePipe, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-active-loans.component.html',
  styleUrl: './counter-active-loans.component.scss',
})
export class CounterActiveLoansComponent implements OnInit {
  private readonly service = inject(CounterService);
  protected readonly context = inject(CounterContext);
  private readonly loads = new Subject<void>();

  protected readonly term = signal('');
  protected readonly state = signal<LoadState<readonly StaffLoan[]>>({ status: 'loading' });
  protected readonly limit = LIST_LIMIT;

  /** Contadores do que está listado (respeitam a busca e o filtro de cliente). */
  protected readonly counters = computed(() => {
    const s = this.state();
    if (s.status !== 'loaded') return null;
    const overdue = s.data.filter((loan) => loan.status === 'OVERDUE').length;
    return { active: s.data.length - overdue, overdue };
  });

  constructor() {
    this.loads
      .pipe(
        switchMap(() =>
          toLoadState(
            this.service.listLoans({ q: this.term(), clientId: this.context.client()?.id }),
            'Não foi possível carregar os empréstimos ativos.',
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

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
  }

  protected search(event: Event): void {
    event.preventDefault();
    this.reload();
  }

  protected clearClient(): void {
    this.context.client.set(null);
    this.reload();
  }
}
