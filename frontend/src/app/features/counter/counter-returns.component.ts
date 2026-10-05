import { ActivatedRoute } from '@angular/router';
import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { SaveFailureComponent } from './save-failure.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { CounterService, LIST_LIMIT, StaffLoan } from './counter.service';
import { ActionFlow, toLoadState } from './desk-flow';
import { ReceiptComponent } from '../receipts/receipt.component';

/**
 * Frame "Funcionário / Devolução": abre listando os empréstimos em aberto (`GET /staff/loans`, já ordenado por
 * vencimento, logo com os atrasados primeiro) e a busca por exemplar, ISBN, cliente ou obra filtra a lista
 * (Issue #180). Registra a devolução com confirmação (`POST /staff/loans/{id}/confirm-return`).
 */
@Component({
  selector: 'app-counter-returns',
  standalone: true,
  imports: [SaveFailureComponent, DatePipe, AlertComponent, SpinnerComponent, ConfirmDialogComponent, ReceiptComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-returns.component.html',
  styleUrl: './counter-returns.component.scss',
})
export class CounterReturnsComponent implements OnInit {
  private readonly service = inject(CounterService);
  private readonly initialTerm = inject(ActivatedRoute, { optional: true })?.snapshot.queryParamMap.get('q') ?? '';
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly searches = new Subject<void>();

  protected readonly term = signal(this.initialTerm);
  /** Termo da última busca enviada (vazio = lista padrão); é ele que a recarga reutiliza. */
  protected readonly searched = signal(this.initialTerm);
  protected readonly limit = LIST_LIMIT;
  /** Empréstimo cuja devolução acabou de ser registrada; abre o comprovante de devolução. */
  protected readonly returnedLoanId = signal<number | null>(null);
  protected readonly state = signal<LoadState<readonly StaffLoan[]>>({ status: 'loading' });

  protected readonly flow = new ActionFlow(inject(DestroyRef), () => {
    this.reload();
    queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('[data-feedback]')?.focus());
  });

  constructor() {
    this.searches
      .pipe(
        switchMap(() =>
          toLoadState(
            this.service.listLoans({ q: this.searched() }),
            'Não foi possível carregar os empréstimos. Tente novamente.',
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }

  ngOnInit(): void {
    this.reload();
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
  }

  protected search(event: Event): void {
    event.preventDefault();
    this.flow.saveFailed.set(false);
    this.searched.set(this.term().trim());
    this.reload();
  }

  protected reload(): void {
    this.searches.next();
  }

  protected confirmReturn(loan: StaffLoan): void {
    this.flow.ask({
      title: 'Confirmar devolução?',
      details: [
        `Cliente: ${loan.client.name} (${loan.client.email})`,
        `Obra: ${loan.book.title}`,
        `Exemplar: ${loan.copy_barcode}`,
        loan.status === 'OVERDUE' ? `Empréstimo em atraso há ${loan.days_late} dia(s).` : 'Empréstimo dentro do prazo.',
      ],
      confirmLabel: 'Confirmar devolução',
      run: () => this.service.confirmReturn(loan.id),
      success: () => `Devolução confirmada: exemplar ${loan.copy_barcode} de “${loan.book.title}”.`,
      done: (result) => this.returnedLoanId.set(result.id),
    });
  }
}
