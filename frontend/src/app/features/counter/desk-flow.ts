import { DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, catchError, finalize, map, of, startWith } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { CopyDestination, CopyStatus, StaffCatalogCopy } from './counter.service';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';
import { errorMessage } from './desk-panel';
import { isPersistenceFailure, showFailure } from './save-failure';

/** Converte uma consulta em estados de tela (carregando, carregado, erro de domínio). */
export function toLoadState<T>(source: Observable<T>, fallback: string): Observable<LoadState<T>> {
  return source.pipe(
    map((data): LoadState<T> => ({ status: 'loaded', data })),
    startWith<LoadState<T>>({ status: 'loading' }),
    catchError((error) => of<LoadState<T>>({ status: 'error', message: errorMessage(error, fallback) })),
  );
}

/** Operação que só roda depois da confirmação explícita do funcionário. */
export interface PendingAction<R = unknown> {
  readonly title: string;
  readonly intro?: string;
  readonly detailsTitle?: string;
  readonly details: readonly string[];
  readonly confirmLabel: string;
  readonly run: () => Observable<R>;
  readonly success: (result: R) => string;
  /** Chamado com o resultado após o 2xx (ex.: abrir o comprovante). */
  readonly done?: (result: R) => void;
  /** Trata o erro por conta própria (ex.: tela de bloqueio); retornar true suprime o feedback genérico. */
  readonly onError?: (error: unknown) => boolean;
}

/**
 * Confirmação antes de alterar dados, bloqueio de envio duplicado e feedback somente após a resposta.
 * Sucesso (2xx) e recusas de domínio (4xx) vão para o snackbar; falha de persistência ou de rede (0/5xx) liga
 * `saveFailed` (estado "Não foi possível salvar"), sem reenvio automático.
 * `after` é chamado depois de qualquer resposta (sucesso ou erro) para recarregar a tela.
 */
export class ActionFlow {
  readonly confirming = signal<PendingAction<any> | null>(null);
  readonly submitting = signal(false);
  readonly saveFailed = signal(false);
  private readonly snackbar = inject(SnackbarService);

  constructor(
    private readonly destroyRef: DestroyRef,
    private readonly after: (succeeded: boolean) => void,
  ) {}

  ask<R>(action: PendingAction<R>): void {
    if (this.submitting()) return;
    this.saveFailed.set(false);
    this.confirming.set(action);
  }

  cancel(): void {
    if (!this.submitting()) this.confirming.set(null);
  }

  confirm(): void {
    const action = this.confirming();
    if (!action || this.submitting()) return;
    this.submitting.set(true);
    this.saveFailed.set(false);
    action
      .run()
      .pipe(
        finalize(() => this.submitting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (result) => {
          this.confirming.set(null);
          this.snackbar.show(action.success(result), 'success');
          action.done?.(result);
          this.after(true);
        },
        error: (error) => {
          this.confirming.set(null);
          if (action.onError?.(error)) {
            // A tela decide como explicar (ex.: cartão de bloqueio).
          } else if (isPersistenceFailure(error)) {
            this.saveFailed.set(true);
          } else {
            showFailure(this.snackbar, error, 'Não foi possível concluir a operação. Tente novamente.');
          }
          this.after(false);
        },
      });
  }
}

const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

/** Preço decimal vindo da API (texto ou número) em reais; travessão quando ausente. */
export function formatPrice(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const amount = Number(value);
  return Number.isFinite(amount) ? BRL.format(amount) : '—';
}

export function destinationLabel(destination: CopyDestination): string {
  return destination === 'COMMERCIAL' ? 'Venda' : 'Empréstimo';
}

const STATUS_LABEL: Readonly<Partial<Record<CopyStatus, string>>> = {
  AVAILABLE: 'Venda em andamento',
  BORROWED: 'Emprestado',
  RESERVED: 'Reservado',
  SOLD: 'Vendido',
};

/** Situação do exemplar para o balcão, derivada dos fatos que o backend informa. */
export function copyStatusLabel(copy: StaffCatalogCopy): string {
  if (!copy.is_active || copy.status === 'INACTIVE') return 'Inativo';
  if (copy.allocated_for_purchase) return 'Reservado para venda';
  if (copy.free) return 'Disponível';
  return STATUS_LABEL[copy.status] ?? copy.status;
}
