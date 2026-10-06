import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { CLIENT_SEARCH_LIMIT, CounterService, StaffClient } from './counter.service';
import { toLoadState } from './desk-flow';
import { ineligibleReasons } from './desk-panel';

/**
 * Seleção de cliente do balcão (Issue #172): ao abrir já lista os clientes ativos (`GET /staff/clients` sem termo)
 * e a busca por nome ou e-mail (mínimo de 2 caracteres) funciona como filtro. No empréstimo (`loan`) a lista mostra a
 * elegibilidade; na venda (`sale`) a penalidade não bloqueia a compra, mas cadastro inativo não pode ser escolhido.
 */
@Component({
  selector: 'app-client-picker',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './client-picker.component.html',
  styleUrl: './client-picker.component.scss',
})
export class ClientPickerComponent {
  private readonly service = inject(CounterService);
  private readonly searches = new Subject<void>();

  @Input() inputId = 'client-q';
  @Input() mode: 'loan' | 'sale' = 'loan';
  @Output() readonly picked = new EventEmitter<StaffClient>();

  protected readonly limit = CLIENT_SEARCH_LIMIT;
  protected readonly ineligibleReasons = ineligibleReasons;
  protected readonly term = signal('');
  /** Termo aplicado à lista atual; vazio é a lista padrão de clientes ativos. */
  protected readonly applied = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly state = signal<LoadState<readonly StaffClient[]> | null>(null);

  constructor() {
    this.searches
      .pipe(
        switchMap(() =>
          toLoadState(this.service.searchClients(this.applied() || undefined), 'Não foi possível buscar os clientes. Tente novamente.'),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
    this.reload();
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
    this.error.set(null);
  }

  protected search(event: Event): void {
    event.preventDefault();
    const term = this.term().trim();
    if (term.length === 1) {
      this.error.set('Informe ao menos 2 caracteres do nome ou do e-mail.');
      return;
    }
    this.applied.set(term);
    this.reload();
  }

  protected reload(): void {
    this.searches.next();
  }

  protected selectable(client: StaffClient): boolean {
    return this.mode === 'sale' ? client.is_active : true;
  }

  protected meta(client: StaffClient): string {
    if (this.mode === 'loan') {
      return `${client.email} · ${client.eligible ? 'apto' : 'não apto: ' + ineligibleReasons(client).join(', ')}`;
    }
    if (!client.is_active) return `${client.email} · cadastro inativo: não pode comprar`;
    return client.is_penalized ? `${client.email} · penalizado (não bloqueia a venda)` : client.email;
  }
}
