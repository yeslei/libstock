import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, catchError, finalize, of, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { CounterService, StaffPurchaseReservation } from './counter.service';
import { errorMessage, ineligibleReasons } from './desk-panel';
import { toLoadState } from './desk-flow';
import { canSellReservation } from './reservation-queue';

type Step = 'check' | 'confirm' | 'done';
type Screen = 'missing' | 'expired' | 'unavailable' | Step;

interface Completed {
  readonly reservation: StaffPurchaseReservation;
  readonly saleId: number;
  /** Próxima reserva aguardando da obra, lida de uma nova consulta; `null` se não houver ou a consulta falhar. */
  readonly next: StaffPurchaseReservation | null;
}

/**
 * Complemento 02 (atender, confirmar e venda concluída) e 07 (reserva fora do prazo). `GET /staff/purchase-reservations`
 * localiza a reserva (o filtro `cliente` da URL a restringe ao cliente), o código digitado é comparado ao exemplar
 * destinado devolvido pelo backend e `POST /staff/purchase-reservations/{id}/confirm-sale` conclui a venda.
 * A tela de sucesso só aparece depois de 2xx; o fora do prazo só aparece quando o backend informa `expired`.
 */
@Component({
  selector: 'app-counter-reservation-attend',
  standalone: true,
  imports: [DatePipe, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-reservation-attend.component.html',
  styleUrl: './counter-reservation-attend.component.scss',
})
export class CounterReservationAttendComponent {
  private readonly service = inject(CounterService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly loads = new Subject<void>();

  /** Parâmetros da rota (`withComponentInputBinding`) ou informados diretamente nos testes. */
  readonly id = input.required<string | number>();
  readonly cliente = input<string | number | null | undefined>(null);

  protected readonly ineligibleReasons = ineligibleReasons;
  protected readonly state = signal<LoadState<StaffPurchaseReservation | null>>({ status: 'loading' });
  protected readonly step = signal<Step>('check');
  protected readonly code = signal('');
  protected readonly codeError = signal<string | null>(null);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly completed = signal<Completed | null>(null);

  protected readonly screen = computed<Screen | null>(() => {
    if (this.completed()) return 'done';
    const s = this.state();
    if (s.status !== 'loaded') return null;
    const reservation = s.data;
    if (!reservation) return 'missing';
    if (reservation.expired) return 'expired';
    if (reservation.status !== 'NOTIFIED' || reservation.allocated_copy_id === null) return 'unavailable';
    return this.step();
  });

  constructor() {
    this.loads
      .pipe(
        switchMap(() => {
          const client = Number(this.cliente());
          const id = Number(this.id());
          return toLoadState(
            this.service
              .listPurchaseReservations({ clientId: Number.isInteger(client) && client > 0 ? client : null })
              .pipe(switchMap((list) => of(list.find((r) => r.id === id) ?? null))),
            'Não foi possível carregar a reserva. Tente novamente.',
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
    // Os parâmetros da rota chegam depois do construtor; qualquer mudança de reserva ou cliente recarrega.
    effect(() => {
      this.id();
      this.cliente();
      untracked(() => this.reload());
    });
  }

  protected reload(): void {
    this.loads.next();
  }

  protected canSell(reservation: StaffPurchaseReservation): boolean {
    return canSellReservation(reservation);
  }

  protected setCode(event: Event): void {
    this.code.set((event.target as HTMLInputElement).value);
    this.codeError.set(null);
  }

  /** "Conferir venda": o código entregue deve ser o do exemplar destinado pelo backend; sem regra nova. */
  protected check(event: Event, reservation: StaffPurchaseReservation): void {
    event.preventDefault();
    if (!this.canSell(reservation)) return;
    const typed = this.code().trim();
    if (!typed) {
      this.codeError.set('Informe o código do exemplar entregue.');
      return;
    }
    if (typed !== reservation.allocated_copy_barcode) {
      this.codeError.set('O código informado não corresponde ao exemplar destinado a esta reserva. Confira o exemplar entregue.');
      return;
    }
    this.error.set(null);
    this.step.set('confirm');
    this.focusHeading();
  }

  protected back(): void {
    if (this.submitting()) return;
    this.step.set('check');
    this.focusHeading();
  }

  protected confirm(reservation: StaffPurchaseReservation): void {
    if (this.submitting() || !this.canSell(reservation)) return;
    this.submitting.set(true);
    this.error.set(null);
    this.service
      .confirmSale(reservation.id)
      .pipe(
        finalize(() => this.submitting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (result) => {
          this.completed.set({ reservation, saleId: result.id, next: null });
          this.loadNext(reservation, result.id);
          this.focusHeading();
        },
        error: (error) => {
          this.error.set(errorMessage(error, 'Não foi possível concluir a venda. Tente novamente.'));
          this.reload();
          this.focusHeading();
        },
      });
  }

  private loadNext(reservation: StaffPurchaseReservation, saleId: number): void {
    this.service
      .listPurchaseReservations({ q: reservation.book.title })
      .pipe(
        catchError(() => of<StaffPurchaseReservation[]>([])),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((list) => {
        const next =
          list
            .filter((r) => r.book.id === reservation.book.id && r.status === 'WAITING')
            .sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0))[0] ?? null;
        this.completed.set({ reservation, saleId, next });
      });
  }

  private focusHeading(): void {
    queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('h1')?.focus());
  }
}
