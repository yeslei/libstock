import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, EventEmitter, Output, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, catchError, map, of, startWith, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { CLIENT_SEARCH_LIMIT, ClientPendencies, CounterService, StaffClient } from './counter.service';
import { errorMessage } from './desk-panel';

export type DeskTab = 'retiradas' | 'devolucoes' | 'reservas';

export interface ClientNavigation {
  readonly client: StaffClient;
  readonly tab: DeskTab;
}

export const MIN_SEARCH_LENGTH = 2;

@Component({
  selector: 'app-clients-panel',
  standalone: true,
  imports: [DatePipe, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './clients-panel.component.html',
  styleUrl: './clients-panel.component.scss',
})
export class ClientsPanelComponent {
  private readonly service = inject(CounterService);
  private readonly destroyRef = inject(DestroyRef);

  @Output() readonly open = new EventEmitter<ClientNavigation>();

  protected readonly term = signal('');
  protected readonly tooShort = signal(false);
  /** Termo aplicado à lista; vazio é a lista padrão de clientes ativos (Issue #172). */
  protected readonly applied = signal('');
  protected readonly results = signal<LoadState<readonly StaffClient[]> | null>(null);
  protected readonly selected = signal<StaffClient | null>(null);
  protected readonly pendencies = signal<LoadState<ClientPendencies> | null>(null);
  protected readonly minLength = MIN_SEARCH_LENGTH;
  protected readonly limit = CLIENT_SEARCH_LIMIT;

  private readonly searches = new Subject<string>();
  private byTerm = false;
  private readonly lookups = new Subject<StaffClient>();

  constructor() {
    this.searches
      .pipe(
        switchMap((term) =>
          this.service.searchClients(term || undefined).pipe(
            map((data): LoadState<readonly StaffClient[]> => ({ status: 'loaded', data })),
            startWith<LoadState<readonly StaffClient[]>>({ status: 'loading' }),
            catchError((error) =>
              of<LoadState<readonly StaffClient[]>>({
                status: 'error',
                message: errorMessage(error, 'Não foi possível buscar clientes. Tente novamente.'),
              }),
            ),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => {
        this.results.set(state);
        // Só uma busca por termo com um único cliente abre a consulta direto; a lista padrão apenas lista.
        if (this.byTerm && state.status === 'loaded' && state.data.length === 1) this.consult(state.data[0]);
      });

    this.lookups
      .pipe(
        switchMap((client) =>
          this.service.getClientPendencies(client.id).pipe(
            map((data): LoadState<ClientPendencies> => ({ status: 'loaded', data })),
            startWith<LoadState<ClientPendencies>>({ status: 'loading' }),
            catchError((error) =>
              of<LoadState<ClientPendencies>>({
                status: 'error',
                message: errorMessage(error, 'Não foi possível consultar as pendências do cliente.'),
              }),
            ),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => this.pendencies.set(state));

    this.searches.next('');
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
  }

  protected search(event: Event): void {
    event.preventDefault();
    const term = this.term().trim();
    this.tooShort.set(term.length > 0 && term.length < MIN_SEARCH_LENGTH);
    if (this.tooShort()) return;
    this.selected.set(null);
    this.pendencies.set(null);
    this.applied.set(term);
    this.byTerm = term.length > 0;
    this.searches.next(term);
  }

  protected retrySearch(): void {
    this.searches.next(this.applied());
  }

  protected consult(client: StaffClient): void {
    this.selected.set(client);
    this.lookups.next(client);
  }

  protected go(client: StaffClient, tab: DeskTab): void {
    this.open.emit({ client, tab });
  }
}
