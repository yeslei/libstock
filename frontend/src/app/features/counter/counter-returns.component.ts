import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { CounterService, StaffLoan } from './counter.service';
import { ActionFlow, toLoadState } from './desk-flow';

/**
 * Frame "Funcionário / Devolução": localiza o empréstimo aberto pelo código do exemplar ou pelo ISBN
 * (`GET /staff/loans?q=`) e registra a devolução com confirmação (`POST /staff/loans/{id}/confirm-return`).
 */
@Component({
  selector: 'app-counter-returns',
  standalone: true,
  imports: [DatePipe, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-returns.component.html',
  styleUrl: './counter-returns.component.scss',
})
export class CounterReturnsComponent {
  private readonly service = inject(CounterService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly searches = new Subject<void>();

  protected readonly term = signal('');
  /** Termo da última busca enviada; é ele que a recarga reutiliza. */
  protected readonly searched = signal('');
  protected readonly missingTerm = signal(false);
  /** `null` até a primeira busca. */
  protected readonly state = signal<LoadState<readonly StaffLoan[]> | null>(null);

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
            'Não foi possível buscar os empréstimos. Tente novamente.',
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
    this.missingTerm.set(false);
  }

  protected search(event: Event): void {
    event.preventDefault();
    const term = this.term().trim();
    if (!term) {
      this.missingTerm.set(true);
      return;
    }
    this.flow.feedback.set(null);
    this.searched.set(term);
    this.reload();
  }

  protected reload(): void {
    if (this.searched()) this.searches.next();
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
    });
  }
}
