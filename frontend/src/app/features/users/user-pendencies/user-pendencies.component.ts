import { ChangeDetectionStrategy, Component, DestroyRef, Input, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ApiError } from '../../../core/models/auth.model';
import { LoadState } from '../../../core/models/load-state.model';
import { ClientPendencies, CounterService } from '../../counter/counter.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';

/**
 * Seção "Pendências" do usuário (somente leitura). Usa a consulta V2 do balcão
 * (`GET /api/v1/staff/clients/{id}/pendencies`), que não sincroniza penalidade;
 * o id do cliente coincide com o id do usuário.
 */
@Component({
  selector: 'app-user-pendencies',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="pendencies" aria-labelledby="pendencies-title">
      <h2 id="pendencies-title">Pendências</h2>
      @if (state(); as current) {
        @switch (current.status) {
          @case ('loading') {
            <p class="pendencies__state" role="status"><app-spinner [size]="16" /> Consultando pendências…</p>
          }
          @case ('error') {
            <app-alert [message]="current.message">
              <button class="pendencies__retry" type="button" (click)="load()">Tentar novamente</button>
            </app-alert>
          }
          @case ('loaded') {
            @if (current.data.overdue_loans.length === 0) {
              <p class="pendencies__ok">Sem pendências ativas</p>
            } @else {
              <p class="pendencies__alert">Pendência ativa</p>
              <ul class="pendencies__list">
                @for (loan of current.data.overdue_loans; track loan.id) {
                  <li>
                    <strong>Empréstimo em atraso: {{ loan.book.title }}</strong>
                    <span>
                      Exemplar #{{ loan.copy_barcode }} • vencimento
                      {{ loan.due_date | date: 'dd/MM/yyyy' : '-0300' }} • {{ loan.days_late }} dia(s) de atraso
                    </span>
                  </li>
                }
              </ul>
            }
            @if (current.data.client.is_penalized) {
              <p class="pendencies__note">O cliente consta como penalizado.</p>
            }
          }
        }
      }
    </section>
  `,
  styles: `
    :host { display: block; }
    h2 { margin: 0 0 0.5rem; font-size: 1.1rem; }
    .pendencies__ok { margin: 0; color: #2f6b3f; font-size: 0.9rem; }
    .pendencies__alert { margin: 0 0 0.5rem; color: #962f29; font-weight: 700; }
    .pendencies__list { display: grid; gap: 0.5rem; margin: 0; padding: 0; list-style: none; }
    .pendencies__list li { display: grid; gap: 0.15rem; padding: 0.5rem 0.75rem; border-left: 4px solid #962f29; background: #f9ecea; }
    .pendencies__list span, .pendencies__note { font-size: 0.875rem; }
    .pendencies__state { display: flex; align-items: center; gap: 0.5rem; margin: 0; }
    .pendencies__retry { min-height: 36px; margin-top: 0.5rem; padding: 0 0.75rem; cursor: pointer; }
  `,
})
export class UserPendenciesComponent implements OnInit {
  private readonly counter = inject(CounterService);
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) userId!: number;

  protected readonly state = signal<LoadState<ClientPendencies>>({ status: 'loading' });

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.state.set({ status: 'loading' });
    this.counter
      .getClientPendencies(this.userId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => this.state.set({ status: 'loaded', data }),
        error: (error: ApiError) =>
          this.state.set({
            status: 'error',
            message: error.detail || 'Não foi possível consultar as pendências.',
          }),
      });
  }
}
