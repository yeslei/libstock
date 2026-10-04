import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { SaveFailureComponent } from './save-failure.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { CounterContext } from './counter-context.service';
import { CounterService, LIST_LIMIT, StaffPurchaseReservation } from './counter.service';
import { ActionFlow, toLoadState } from './desk-flow';
import { BLOCK_TEXT, groupByBook } from './reservation-queue';

/**
 * Frame "Reservas de compra no balcão" (complemento 02, lista) e estado "Nenhuma reserva encontrada"
 * (complemento 07): fila de compra por obra (`GET /staff/purchase-reservations`), destinação de exemplar à
 * primeira reserva (`POST /staff/books/{id}/allocate-purchase`) e acesso a "Atender reserva".
 */
@Component({
  selector: 'app-counter-reservations',
  standalone: true,
  imports: [SaveFailureComponent, DatePipe, RouterLink, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-reservations.component.html',
  styleUrl: './counter-reservations.component.scss',
})
export class CounterReservationsComponent {
  private readonly service = inject(CounterService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly loads = new Subject<void>();

  protected readonly context = inject(CounterContext);
  protected readonly limit = LIST_LIMIT;
  protected readonly blockText = BLOCK_TEXT;
  protected readonly term = signal('');
  /** Termo da última busca enviada; é ele que a recarga reutiliza. */
  protected readonly searched = signal('');
  protected readonly state = signal<LoadState<readonly StaffPurchaseReservation[]>>({ status: 'loading' });
  protected readonly queues = computed(() => {
    const s = this.state();
    return s.status === 'loaded' ? groupByBook(s.data) : [];
  });

  protected readonly hasExpired = computed(() => {
    const s = this.state();
    return s.status === 'loaded' && s.data.some((reservation) => reservation.expired);
  });

  protected readonly flow = new ActionFlow(inject(DestroyRef), () => {
    this.reload();
    queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('[data-feedback]')?.focus());
  });

  constructor() {
    this.loads
      .pipe(
        switchMap(() =>
          toLoadState(
            this.service.listPurchaseReservations({ q: this.searched(), clientId: this.context.client()?.id }),
            'Não foi possível carregar as reservas de compra.',
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
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
    this.loads.next();
  }

  /** "Limpar busca": remove o termo e o filtro de cliente e consulta todas as reservas. */
  protected clearSearch(): void {
    this.term.set('');
    this.searched.set('');
    this.context.client.set(null);
    this.reload();
  }

  protected removeClientFilter(): void {
    this.context.client.set(null);
    this.reload();
  }

  protected focusSearch(): void {
    this.host.nativeElement.querySelector<HTMLInputElement>('#reservation-q')?.focus();
  }

  protected get filtered(): boolean {
    return this.searched() !== '' || this.context.client() !== null;
  }

  protected allocate(reservation: StaffPurchaseReservation): void {
    if (!reservation.can_allocate) return;
    this.flow.ask({
      title: 'Destinar exemplar?',
      details: [
        `Obra: ${reservation.book.title}`,
        `Primeira reserva elegível da fila: ${reservation.client.name} (${reservation.client.email})`,
        `Exemplares comerciais livres: ${reservation.free_commercial_copies}`,
        'Um exemplar comercial livre ficará destinado a este cliente e indisponível para outros, com cinco dias corridos para a retirada.',
      ],
      confirmLabel: 'Destinar exemplar',
      run: () => this.service.allocatePurchase(reservation.book.id),
      success: () => `Exemplar destinado a ${reservation.client.name} para “${reservation.book.title}”.`,
    });
  }

  protected cancel(reservation: StaffPurchaseReservation): void {
    const destined = reservation.status === 'NOTIFIED';
    this.flow.ask({
      title: 'Cancelar reserva?',
      details: [
        `Obra: ${reservation.book.title}`,
        `Cliente: ${reservation.client.name} (${reservation.client.email})`,
        destined
          ? 'O exemplar destinado será liberado e a reserva ficará cancelada.'
          : 'A reserva sairá da fila e ficará cancelada.',
      ],
      confirmLabel: 'Cancelar reserva',
      run: () => this.service.cancelReservation(reservation.id),
      success: () => `Reserva de ${reservation.client.name} para “${reservation.book.title}” cancelada.`,
    });
  }

  protected releaseExpired(): void {
    this.flow.ask({
      title: 'Liberar exemplares vencidos?',
      details: ['As reservas com prazo de retirada vencido passarão a expiradas e seus exemplares voltarão à fila.'],
      confirmLabel: 'Liberar exemplares',
      run: () => this.service.expireDueReservations(),
      success: (result) =>
        result.expired === 1 ? '1 reserva vencida foi encerrada.' : `${result.expired} reservas vencidas foram encerradas.`,
    });
  }
}
