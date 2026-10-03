import { DestroyRef, Directive, ElementRef, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, Subject, catchError, finalize, map, of, startWith, switchMap } from 'rxjs';

import { ApiError } from '../../core/models/auth.model';
import { LoadState } from '../../core/models/load-state.model';
import { CirculationResult, CounterService, StaffClient } from './counter.service';

export interface Feedback {
  readonly kind: 'success' | 'error';
  readonly message: string;
}

/** Operação aguardando confirmação explícita do funcionário antes do POST. */
export interface Confirmation {
  readonly title: string;
  readonly details: readonly string[];
  readonly confirmLabel: string;
  readonly run: () => Observable<CirculationResult>;
  readonly success: (result: CirculationResult) => string;
}

export function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as Partial<ApiError> | null)?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}

export function ineligibleReasons(client: StaffClient): string[] {
  const reasons: string[] = [];
  if (!client.is_active) reasons.push('cadastro inativo');
  if (client.is_penalized) reasons.push('penalizado');
  if (client.has_overdue_loan) reasons.push('empréstimo em atraso');
  return reasons;
}

/**
 * Comportamento comum das abas do balcão: carga/recarga, filtro por termo, confirmação
 * antes de alterar dados, bloqueio de envio duplicado e feedback somente após 2xx.
 */
@Directive()
export abstract class DeskPanel<T> implements OnInit, OnChanges {
  /** Filtro opcional vindo da aba Clientes. */
  @Input() client: StaffClient | null = null;
  @Output() readonly clearClient = new EventEmitter<void>();

  protected readonly service = inject(CounterService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  protected readonly state = signal<LoadState<readonly T[]>>({ status: 'loading' });
  protected readonly term = signal('');
  protected readonly feedback = signal<Feedback | null>(null);
  protected readonly confirming = signal<Confirmation | null>(null);
  protected readonly submitting = signal(false);
  protected readonly ineligibleReasons = ineligibleReasons;

  private readonly requests = new Subject<void>();
  private opener: HTMLElement | null = null;
  private started = false;

  protected abstract fetch(): Observable<T[]>;
  protected abstract readonly loadError: string;

  constructor() {
    this.requests
      .pipe(
        switchMap(() =>
          this.fetch().pipe(
            map((data): LoadState<readonly T[]> => ({ status: 'loaded', data })),
            startWith<LoadState<readonly T[]>>({ status: 'loading' }),
            catchError((error) =>
              of<LoadState<readonly T[]>>({ status: 'error', message: errorMessage(error, this.loadError) }),
            ),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }

  ngOnInit(): void {
    this.started = true;
    this.reload();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['client'] && this.started) this.reload();
  }

  protected reload(): void {
    this.requests.next();
  }

  protected search(event: Event): void {
    event.preventDefault();
    this.reload();
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
  }

  protected ask(confirmation: Confirmation): void {
    if (this.submitting()) return;
    this.opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    this.feedback.set(null);
    this.confirming.set(confirmation);
  }

  protected cancel(): void {
    if (this.submitting()) return;
    this.confirming.set(null);
    this.opener?.focus();
  }

  protected confirm(): void {
    const confirmation = this.confirming();
    if (!confirmation || this.submitting()) return;
    this.submitting.set(true);
    confirmation
      .run()
      .pipe(
        finalize(() => this.submitting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (result) => this.finish({ kind: 'success', message: confirmation.success(result) }),
        error: (error) =>
          this.finish({
            kind: 'error',
            message: errorMessage(error, 'Não foi possível concluir a operação. Tente novamente.'),
          }),
      });
  }

  private finish(feedback: Feedback): void {
    this.confirming.set(null);
    this.feedback.set(feedback);
    this.reload();
    queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('[data-feedback]')?.focus());
  }
}
