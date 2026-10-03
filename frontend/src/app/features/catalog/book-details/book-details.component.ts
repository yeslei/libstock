import { CurrencyPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, startWith, switchMap, takeUntil } from 'rxjs';
import { ClientRequestsService } from '../../client-tracking/client-requests.service';
import { AuthService } from '../../../core/services/auth.service';
import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogBookDetail, LoadState } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';
import { nextMonth, todayInSaoPaulo } from './loan-dates';

@Component({
  selector: 'app-book-details', standalone: true,
  imports: [RouterLink, CurrencyPipe, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './book-details.component.html', styleUrl: './book-details.component.scss',
})
export class BookDetailsComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly catalog = inject(CatalogService);
  private readonly requests = inject(ClientRequestsService);
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
  protected readonly snackbar = signal<string | null>(null);
  protected readonly coverFailed = signal(false);
  protected readonly purchaseDate = signal('');
  protected readonly purchasing = signal(false);
  protected readonly purchaseRequested = signal(false);
  protected readonly purchaseError = signal<string | null>(null);
  private snackbarTimer?: ReturnType<typeof setTimeout>;
  protected readonly state = toSignal(this.route.paramMap.pipe(
    switchMap((params) => {
      this.bookVersion++;
      this.bookChanged.next();
      clearTimeout(this.snackbarTimer);
      this.submitting.set(false); this.purchasing.set(false);
      this.pickupDate.set(''); this.requested.set(false); this.error.set(null);
      this.snackbar.set(null); this.coverFailed.set(false);
      this.purchaseDate.set(''); this.purchaseRequested.set(false); this.purchaseError.set(null);
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
    this.destroyRef.onDestroy(() => clearTimeout(this.snackbarTimer));
  }

  private showSnackbar(message: string): void {
    clearTimeout(this.snackbarTimer);
    this.snackbar.set(message);
    this.snackbarTimer = setTimeout(() => this.snackbar.set(null), 8000);
  }

  protected today(): string { return todayInSaoPaulo(); }

  protected async reservePurchase(book: CatalogBookDetail): Promise<void> {
    if (this.purchasing() || this.purchaseRequested()) return;
    this.purchaseError.set(null); this.purchasing.set(true);
    const version = this.bookVersion;
    await this.auth.restoreSession();
    if (this.destroyRef.destroyed || version !== this.bookVersion) return;
    if (!this.auth.currentUser) {
      this.purchasing.set(false);
      void this.router.navigate(['/login'], { queryParams: { redirectTo: `/livros/${book.id}` } }); return;
    }
    this.requests.reservePurchase(book.id).pipe(takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => { this.purchasing.set(false); this.purchaseRequested.set(true); this.showSnackbar('Reserva de compra realizada com sucesso.'); },
      error: (error: ApiError) => { this.purchasing.set(false); this.purchaseError.set(error.detail ?? 'Não foi possível reservar a compra.'); },
    });
  }

  protected async submitPurchase(event: Event, book: CatalogBookDetail): Promise<void> {
    event.preventDefault();
    if (this.purchasing() || this.purchaseRequested()) return;
    this.purchaseError.set(null);
    if (!nextMonth(this.purchaseDate()) || this.purchaseDate() < this.today()) {
      this.purchaseError.set('Informe uma data de retirada válida, a partir de hoje.'); return;
    }
    this.purchasing.set(true);
    const version = this.bookVersion;
    await this.auth.restoreSession();
    if (this.destroyRef.destroyed || version !== this.bookVersion) return;
    if (!this.auth.currentUser) {
      this.purchasing.set(false);
      void this.router.navigate(['/login'], { queryParams: { redirectTo: `/livros/${book.id}` } }); return;
    }
    this.requests.requestPurchase(book.id, this.purchaseDate()).pipe(takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        this.purchasing.set(false); this.purchaseRequested.set(true); this.purchaseDate.set(response.pickup_date);
        this.showSnackbar('Solicitação de compra realizada com sucesso.');
      },
      error: (error: ApiError) => { this.purchasing.set(false); this.purchaseError.set(error.detail ?? 'Não foi possível salvar a solicitação de compra.'); },
    });
  }

  protected async submit(event: Event, book: CatalogBookDetail): Promise<void> {
    event.preventDefault();
    if (this.submitting() || this.requested()) return;
    this.error.set(null);
    if (!this.dueDate() || this.pickupDate() < this.today()) {
      this.error.set('Informe uma data de retirada válida, a partir de hoje.'); return;
    }
    this.submitting.set(true);
    const version = this.bookVersion;
    await this.auth.restoreSession();
    if (this.destroyRef.destroyed || version !== this.bookVersion) return;
    if (!this.auth.currentUser) {
      this.submitting.set(false);
      void this.router.navigate(['/login'], { queryParams: { redirectTo: `/livros/${book.id}` } });
      return;
    }
    this.requests.requestLoan(book.id, this.pickupDate()).pipe(takeUntil(this.bookChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        this.submitting.set(false); this.requested.set(true);
        this.pickupDate.set(response.pickup_date);
        this.showSnackbar('Solicitação de empréstimo realizada com sucesso.');
      },
      error: (error: ApiError) => {
        this.submitting.set(false);
        this.error.set(error.detail ?? 'Não foi possível salvar a solicitação. Tente novamente.');
      },
    });
  }
}
