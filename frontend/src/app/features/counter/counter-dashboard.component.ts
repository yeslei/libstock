import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, catchError, map, of, startWith, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { CounterService, StaffDashboard } from './counter.service';
import { errorMessage } from './desk-panel';

interface AccessCard {
  readonly title: string;
  readonly description: string;
  readonly route: string;
}

interface Indicator {
  readonly key: keyof StaffDashboard;
  readonly label: string;
}

/** Cartões de acesso rápido, na ordem visual do Figma (Funcionário / Painel). */
const ACCESS: readonly AccessCard[] = [
  { title: 'Consultar acervo', description: 'Buscar obras e disponibilidade', route: '/balcao/acervo' },
  { title: 'Registrar devolução', description: 'Dar baixa em um exemplar', route: '/balcao/devolucoes' },
  { title: 'Vendas', description: 'Venda de acervo comercial', route: '/balcao/vendas' },
  { title: 'Empréstimo', description: 'Registrar um novo empréstimo', route: '/balcao/emprestimos/novo' },
];

const INDICATORS: readonly Indicator[] = [
  { key: 'active_loans', label: 'Empréstimos ativos' },
  { key: 'returns_today', label: 'Devoluções hoje' },
  { key: 'waiting_reservations', label: 'Reservas aguardando' },
  { key: 'pendencies', label: 'Pendências' },
];

@Component({
  selector: 'app-counter-dashboard',
  standalone: true,
  imports: [RouterLink, AlertComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-dashboard.component.html',
  styleUrl: './counter-dashboard.component.scss',
})
export class CounterDashboardComponent implements OnInit {
  private readonly service = inject(CounterService);
  private readonly loads = new Subject<void>();

  protected readonly access = ACCESS;
  protected readonly indicators = INDICATORS;
  protected readonly state = signal<LoadState<StaffDashboard>>({ status: 'loading' });

  constructor() {
    this.loads
      .pipe(
        switchMap(() =>
          this.service.getDashboard().pipe(
            map((data): LoadState<StaffDashboard> => ({ status: 'loaded', data })),
            startWith<LoadState<StaffDashboard>>({ status: 'loading' }),
            catchError((error) =>
              of<LoadState<StaffDashboard>>({
                status: 'error',
                message: errorMessage(error, 'Não foi possível carregar os indicadores do painel.'),
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

  protected value(state: LoadState<StaffDashboard>, key: keyof StaffDashboard): string {
    return state.status === 'loaded' ? String(state.data[key]) : '—';
  }
}
