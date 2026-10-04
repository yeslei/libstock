import { CurrencyPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, startWith, switchMap, takeUntil } from 'rxjs';
import { ClientRequestsService } from '../../client-tracking/client-requests.service';
import { ClientTrackingService, TrackingItem } from '../../client-tracking/client-tracking.service';
import { AuthService } from '../../../core/services/auth.service';
import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SnackbarComponent } from '../../../shared/components/snackbar/snackbar.component';
import { SnackbarService } from '../../../shared/components/snackbar/snackbar.service';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogBookDetail, LoadState } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';
import { nextMonth, pickupDeadline, todayInSaoPaulo } from './loan-dates';

/** Tipo de operação do cliente, usado nos textos de bloqueio por pendência. */
export type RequestKind = 'loan' | 'purchase' | 'reservation';
export interface BlockedState {
  readonly kind: RequestKind;
  readonly message: string;
  /** Empréstimos em atraso lidos de `GET /loans/me`; vazio quando a pendência não vem de um empréstimo. */
  readonly overdue: readonly TrackingItem[];
}

const BLOCKED_COPY: Record<RequestKind, { title: string; heading: string; retry: string }> = {
  reservation: { title: 'Reserva bloqueada por pendência', heading: 'Não foi possível registrar a reserva', retry: 'tente reservar novamente' },
  loan: { title: 'Solicitação bloqueada por pendência', heading: 'Não foi possível registrar a solicitação de empréstimo', retry: 'tente solicitar novamente' },
  purchase: { title: 'Solicitação bloqueada por pendência', heading: 'Não foi possível registrar a solicitação de compra', retry: 'tente solicitar novamente' },
};

@Component({
  selector: 'app-book-details', standalone: true,
  imports: [RouterLink, CurrencyPipe, DatePipe, AlertComponent, SnackbarComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './book-details.component.html', styleUrl: './book-details.component.scss',
})
export class BookDetailsComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly catalog = inject(CatalogService);
  private readonly requests = inject(ClientRequestsService);
  private readonly tracking = inject(ClientTrackingService);
  private readonly snackbar = inject(SnackbarService);
  private readonly bookChanged = new Subject<void>();
  private bookVersion = 0;
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly user = toSignal(this.auth.user$, { initialValue: null });
  protected readonly pickupDate = signal('');
  protected readonly dueDate = computed(() => nextMonth(this.pickupDate()));
  protected readonly submitting = signal(false);
  protected readonly requested = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly errorCode = signal<string | null>(null);
  protected readonly coverFailed = signal(false);
  protected readonly purchaseDate = signal('');
  protected readonly purchasing = signal(false);
  protected readonly purchaseRequested = signal(false);
  protected readonly purchaseError = signal<string | null>(null);
  /** Etapa da reserva de compra: confirmação antes de criar e resultado após a resposta 2xx. */
  protected readonly reserveStep = signal<'idle' | 'confirm' | 'done'>('idle');
  protected readonly queuePosition = signal<number | null>(null);
  protected readonly blocked = signal<BlockedState | null>(null);
  protected readonly blockedCopy = computed(() => { const b = this.blocked(); return b ? BLOCKED_COPY[b.kind] : null; });
  protected readonly state = toSignal(this.route.paramMap.pipe(
    switchMap((params) => {
      this.bookVersion++;
      this.bookChanged.next();
      this.snackbar.dismiss();
      this.submitting.set(false); this.purchasing.set(false);
      this.pickupDate.set(''); this.requested.set(false); this.error.set(null); this.errorCode.set(null);
      this.coverFailed.set(false);
      this.purchaseDate.set(''); this.purchaseRequested.set(false); this.purchaseError.set(null);
      this.reserveStep.set('idle'); this.queuePosition.set(null); this.blocked.set(null);
      const id = Number(params.get('id'));
      if (!Number.isSafeInteger(id) || id <= 0) return of<LoadState<CatalogBookDetail>>({ status: 'error', message: 'Livro não encontrado.' });
      return this.catalog.getBook(id).pipe(
        map((data): LoadState<CatalogBookDetail> => ({ status: 'loaded', data })),
        startWith<LoadState<CatalogBookDetail>>({ status: 'loading' }),
        catchError((error: ApiError) => of<LoadState<CatalogBookDetail>>({ status: 'error', message: error.status === 404 ? 'Livro não encontrado.' : 'Não foi possível carregar o livro. Tente novamente.' })),
      );
    }),
  ), { initialValue: { status: 'loading' } as LoadState<CatalogBookDetail> });

  constructor() {
    this.destroyRef.onDestroy(() => this.snackbar.dismiss());
  }

  protected today(): string { return todayInSaoPaulo(); }
  /** Limite da data de retirada: a compra com exemplar destinado vence 5 dias corridos após a solicitação. */
  protected purchaseMax(): string { return pickupDeadline(); }

  /** Texto de quantidade conforme a referência: "1 exemplar disponível" / "2 exemplares disponíveis". */
  protected countLabel(count: number | null, suffix = ''): string {
    if (!count) return 'Esgotado';
    return `${count} ${count === 1 ? 'exemplar disponível' : 'exemplares disponíveis'}${suffix}`;
  }

  /** Modalidade aberta inicialmente: a primeira em que o cliente pode agir. */
  protected openModality(book: CatalogBookDetail): 'loan' | 'sale' | null {
    if (book.availability.loan.available) return 'loan';
    if (book.availability.sale.available || book.availability.sale.can_reserve) return 'sale';
    return null;
  }

  protected backToBook(): void {
    this.blocked.set(null); this.reserveStep.set('idle');
  }

  protected duplicateLink(code: string | null): string | null {
    if (code === 'loan_request_duplicate') return '/meus-emprestimos';
    if (code === 'purchase_request_duplicate' || code === 'reservation_duplicate') return '/minhas-reservas';
    return null;
  }

  private handleFailure(kind: RequestKind, error: ApiError, fallback: string, set: (message: string) => void): void {
    if (error.code === 'client_ineligible') { this.showBlocked(kind, error.detail ?? fallback); return; }
    this.errorCode.set(error.code ?? null);
    set(error.detail ?? fallback);
  }

  /** Mostra o bloqueio e, só para leitura, quais empréstimos em atraso o originam. */
  private showBlocked(kind: RequestKind, message: string): void {
    const version = this.bookVersion;
    this.blocked.set({ kind, message, overdue: [] });
    this.tracking.getLoans().pipe(catchError(() => of<TrackingItem[]>([])), takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe((items) => {
      if (version !== this.bookVersion) return;
      this.blocked.update((current) => current && { ...current, overdue: items.filter((item) => item.status === 'OVERDUE') });
    });
  }

  private async ensureSession(book: CatalogBookDetail, release: () => void): Promise<boolean> {
    const version = this.bookVersion;
    await this.auth.restoreSession();
    if (this.destroyRef.destroyed || version !== this.bookVersion) return false;
    if (!this.auth.currentUser) {
      release();
      void this.router.navigate(['/login'], { queryParams: { redirectTo: `/livros/${book.id}` } });
      return false;
    }
    return true;
  }

  /** Primeira etapa da reserva: abre a confirmação, sem criar nada. */
  protected async startReservation(book: CatalogBookDetail): Promise<void> {
    if (this.purchasing() || this.purchaseRequested()) return;
    this.purchaseError.set(null); this.errorCode.set(null); this.purchasing.set(true);
    const proceed = await this.ensureSession(book, () => this.purchasing.set(false));
    if (!proceed) return;
    this.purchasing.set(false);
    this.reserveStep.set('confirm');
  }

  protected confirmReservation(book: CatalogBookDetail): void {
    if (this.purchasing() || this.purchaseRequested()) return;
    this.purchaseError.set(null); this.errorCode.set(null); this.purchasing.set(true);
    this.requests.reservePurchase(book.id).pipe(takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        this.purchasing.set(false); this.purchaseRequested.set(true);
        this.queuePosition.set(response.queue_position ?? null); this.reserveStep.set('done');
        this.snackbar.show('Reserva de compra realizada com sucesso.', 'success');
      },
      error: (error: ApiError) => {
        this.purchasing.set(false); this.reserveStep.set('idle');
        this.handleFailure('reservation', error, 'Não foi possível reservar a compra.', (m) => this.purchaseError.set(m));
      },
    });
  }

  protected async submitPurchase(event: Event, book: CatalogBookDetail): Promise<void> {
    event.preventDefault();
    if (this.purchasing() || this.purchaseRequested()) return;
    this.purchaseError.set(null); this.errorCode.set(null);
    if (!nextMonth(this.purchaseDate()) || this.purchaseDate() < this.today()) {
      this.purchaseError.set('Informe uma data de retirada válida, a partir de hoje.'); return;
    }
    if (this.purchaseDate() > this.purchaseMax()) {
      this.purchaseError.set('A data de retirada não pode passar de ' + this.purchaseMax().split('-').reverse().join('/') + ', o prazo de retirada da reserva (5 dias corridos).'); return;
    }
    this.purchasing.set(true);
    if (!(await this.ensureSession(book, () => this.purchasing.set(false)))) return;
    this.requests.requestPurchase(book.id, this.purchaseDate()).pipe(takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        this.purchasing.set(false); this.purchaseRequested.set(true); this.purchaseDate.set(response.pickup_date);
        this.snackbar.show(response.reservation_status === 'WAITING'
          ? 'Solicitação registrada no fim da fila de compra. A retirada depende de um exemplar ser destinado a você.'
          : 'Solicitação de compra realizada com sucesso.', 'success');
      },
      error: (error: ApiError) => {
        this.purchasing.set(false);
        this.handleFailure('purchase', error, 'Não foi possível salvar a solicitação de compra.', (m) => this.purchaseError.set(m));
      },
    });
  }

  protected async submit(event: Event, book: CatalogBookDetail): Promise<void> {
    event.preventDefault();
    if (this.submitting() || this.requested()) return;
    this.error.set(null); this.errorCode.set(null);
    if (!this.dueDate() || this.pickupDate() < this.today()) {
      this.error.set('Informe uma data de retirada válida, a partir de hoje.'); return;
    }
    this.submitting.set(true);
    if (!(await this.ensureSession(book, () => this.submitting.set(false)))) return;
    this.requests.requestLoan(book.id, this.pickupDate()).pipe(takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        this.submitting.set(false); this.requested.set(true);
        this.pickupDate.set(response.pickup_date);
        this.snackbar.show('Solicitação de empréstimo realizada com sucesso.', 'success');
      },
      error: (error: ApiError) => {
        this.submitting.set(false);
        this.handleFailure('loan', error, 'Não foi possível salvar a solicitação. Tente novamente.', (m) => this.error.set(m));
      },
    });
  }
}
