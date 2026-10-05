import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { Subject, catchError, forkJoin, map, of, startWith, switchMap } from 'rxjs';
import { LoadState } from '../../core/models/load-state.model';
import { AuthService } from '../../core/services/auth.service';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { StaffIconComponent } from '../../shared/components/staff-icon.component';
import { CounterService, StaffDashboard } from './counter.service';
import { errorMessage } from './desk-panel';
import { DashboardOverview } from './dashboard/dashboard.models';
import { WeeklyMovementComponent } from './dashboard/weekly-movement.component';
import { CategoryChartComponent } from './dashboard/category-chart.component';
import { StatCardComponent } from './dashboard/stat-card.component';
import { RecentMovementsComponent } from './dashboard/recent-movements.component';

type DashboardData = StaffDashboard & DashboardOverview;
@Component({
  selector: 'app-counter-dashboard',
  standalone: true,
  imports: [
    RouterLink,
    AlertComponent,
    StaffIconComponent,
    WeeklyMovementComponent,
    CategoryChartComponent,
    StatCardComponent,
    RecentMovementsComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-dashboard.component.html',
  styleUrl: './counter-dashboard.component.scss',
})
export class CounterDashboardComponent implements OnInit {
  private readonly service = inject(CounterService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly loads = new Subject<void>();
  protected readonly account = this.auth.currentUser;
  protected readonly initials = (this.account?.name ?? 'LibStock')
    .split(' ')
    .slice(0, 2)
    .map((n) => n[0])
    .join('');
  protected readonly state = signal<LoadState<DashboardData>>({ status: 'loading' });
  protected readonly metrics = [
    { key: 'loans_today', label: 'Empréstimos do dia', note: 'Registrados hoje' },
    { key: 'returns_today', label: 'Devoluções do dia', note: 'Exemplares devolvidos hoje' },
    { key: 'waiting_reservations', label: 'Reservas aguardando', note: 'Na fila de compra' },
    { key: 'pendencies', label: 'Pendências', note: 'Clientes com empréstimos em atraso' },
  ] as const;
  constructor() {
    this.loads
      .pipe(
        switchMap(() =>
          forkJoin({
            counts: this.service.getDashboard(),
            overview: this.service.getDashboardOverview(),
          }).pipe(
            map(
              ({ counts, overview }): LoadState<DashboardData> => ({
                status: 'loaded',
                data: { ...counts, ...overview },
              }),
            ),
            startWith<LoadState<DashboardData>>({ status: 'loading' }),
            catchError((error) =>
              of<LoadState<DashboardData>>({
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
  protected value(key: (typeof this.metrics)[number]['key']): string {
    const state = this.state();
    return state.status === 'loaded' ? String(state.data[key]) : '—';
  }
  protected logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/']));
  }
}
