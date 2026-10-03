import { AsyncPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, startWith, switchMap } from 'rxjs';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { LoadState } from '../../core/models/load-state.model';
import { ClientTrackingService, TrackingItem } from './client-tracking.service';

@Component({
  selector: 'app-client-tracking', standalone: true,
  imports: [AsyncPipe, DatePipe, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './client-tracking.component.html', styleUrl: './client-tracking.component.scss',
})
export class ClientTrackingComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(ClientTrackingService);
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
  protected failCover(url: string) { this.failedCovers.update(values => new Set([...values, url])); }
}
