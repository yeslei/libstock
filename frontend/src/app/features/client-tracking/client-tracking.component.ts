import { AsyncPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, catchError, finalize, map, of, startWith, switchMap } from 'rxjs';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { LoadState } from '../../core/models/load-state.model';
import { SnackbarComponent } from '../../shared/components/snackbar/snackbar.component';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';
import { ConfirmDialogComponent } from '../counter/confirm-dialog.component';
import { showFailure } from '../counter/save-failure';
import { ClientTrackingService, TrackingItem } from './client-tracking.service';

@Component({
  selector: 'app-client-tracking', standalone: true,
  imports: [AsyncPipe, DatePipe, RouterLink, AlertComponent, SpinnerComponent, ConfirmDialogComponent, SnackbarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './client-tracking.component.html', styleUrl: './client-tracking.component.scss',
})
export class ClientTrackingComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(ClientTrackingService);
  private readonly snackbar = inject(SnackbarService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly reservations = this.route.snapshot.data['tracking'] === 'reservations';
  protected readonly title = this.reservations ? 'Minhas reservas' : 'Meus empréstimos';
  protected readonly empty = this.reservations ? 'Você não possui reservas de compra em andamento.' : 'Você não possui empréstimos ou solicitações em andamento.';
  protected readonly failedCovers = signal<ReadonlySet<string>>(new Set());
  protected readonly reload = new Subject<void>();
  protected readonly state$ = this.reload.pipe(startWith(undefined), switchMap(() =>
    (this.reservations ? this.service.getReservations() : this.service.getLoans()).pipe(
      map((data): LoadState<TrackingItem[]> => ({ status: 'loaded', data })),
      startWith<LoadState<TrackingItem[]>>({ status: 'loading' }),
      catchError(() => of<LoadState<TrackingItem[]>>({ status: 'error', message: 'Não foi possível carregar seu acompanhamento. Tente novamente.' })),
    ),
  ));
  protected readonly labels: Record<TrackingItem['status'], string> = {
    AWAITING_PICKUP: 'Aguardando retirada', ACTIVE: 'Empréstimo ativo', OVERDUE: 'Em atraso',
    WAITING: 'Aguardando disponibilidade', NOTIFIED: 'Disponível para retirada',
  };
  /** Reserva cuja confirmação de cancelamento está aberta; o envio fica bloqueado enquanto aguarda a resposta. */
  protected readonly confirming = signal<TrackingItem | null>(null);
  protected readonly submitting = signal(false);
  constructor() { this.destroyRef.onDestroy(() => this.snackbar.dismiss()); }
  protected ask(item: TrackingItem) { if (!this.submitting()) this.confirming.set(item); }
  protected dismissConfirm() { if (!this.submitting()) this.confirming.set(null); }
  protected cancel() {
    const item = this.confirming();
    if (!item || this.submitting()) return;
    this.submitting.set(true);
    this.service.cancelReservation(item.id).pipe(finalize(() => this.submitting.set(false)), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => { this.confirming.set(null); this.snackbar.show('Reserva cancelada.', 'success'); this.reload.next(); },
      error: (error) => { this.confirming.set(null); showFailure(this.snackbar, error, 'Não foi possível cancelar a reserva. Tente novamente.'); this.reload.next(); },
    });
  }
  protected failCover(url: string) { this.failedCovers.update(values => new Set([...values, url])); }
}
