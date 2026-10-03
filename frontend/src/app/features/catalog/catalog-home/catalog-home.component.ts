import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { catchError, map, of, startWith, tap } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogCapability, capabilitiesFor } from '../models/catalog-capabilities';
import { BookAvailability, BookOffer, CatalogBook, Genre, LoadState } from '../models/catalog.model';
import { CatalogAdminService } from '../services/catalog-admin.service';
import { CatalogSearchCriterion, CatalogService } from '../services/catalog.service';

/**
 * Vitrine pública. Qualquer visitante navega sem sessão; o login só é cobrado
 * nas ações transacionais.
 *
 * O que a página oferece além da navegação depende do papel de quem olha —
 * ver `catalog-capabilities.ts`, que traduz as histórias do SRS.
 */
@Component({
  selector: 'app-catalog-home',
  standalone: true,
  imports: [AsyncPipe, NgTemplateOutlet, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './catalog-home.component.html',
  styleUrl: './catalog-home.component.scss',
})
export class CatalogHomeComponent {
  private readonly catalog = inject(CatalogService);
  private readonly catalogAdmin = inject(CatalogAdminService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  private readonly user = toSignal(this.auth.user$, { initialValue: null });

  private readonly capabilities = computed<Set<CatalogCapability>>(() =>
    capabilitiesFor(this.user()?.role_codes ?? []),
  );

  protected readonly canManageCatalog = computed(() => this.capabilities().has('manageCatalog'));
  protected readonly isAuthenticated = computed(() => this.user() !== null);
  protected readonly canServeCounter = computed(() => this.capabilities().has('counterService'));
  protected readonly canManageStock = computed(() => this.capabilities().has('manageStock'));
  protected readonly canRegisterCopy = computed(() => this.capabilities().has('registerCopy'));

  /** Livros retirados do destaque nesta sessão, para sumirem sem recarregar. */
  private readonly unfeatured = signal<ReadonlySet<number>>(new Set());
  protected readonly featuredError = signal<string | null>(null);
  protected readonly availability = signal<Record<number, LoadState<BookAvailability>>>({});

  protected readonly genres$ = this.catalog.getFeaturedGenres().pipe(
    map((data): LoadState<Genre[]> => ({ status: 'loaded', data })),
    startWith<LoadState<Genre[]>>({ status: 'loading' }),
    catchError(() =>
      of<LoadState<Genre[]>>({
        status: 'error',
        message: 'Não foi possível carregar as categorias.',
      }),
    ),
  );

  protected readonly books$ = this.catalog.getFeaturedBooks().pipe(
    tap((books) => this.loadAvailability(books)),
    map((data): LoadState<CatalogBook[]> => ({ status: 'loaded', data })),
    startWith<LoadState<CatalogBook[]>>({ status: 'loading' }),
    catchError(() =>
      of<LoadState<CatalogBook[]>>({
        status: 'error',
        message: 'Não foi possível carregar os livros em destaque.',
      }),
    ),
  );

  protected readonly searchCriterion = signal<CatalogSearchCriterion>('title');
  protected readonly searchValue = signal('');
  protected readonly searchState = signal<LoadState<CatalogBook[]> | null>(null);

  protected setSearchCriterion(value: string): void {
    this.searchCriterion.set(value as CatalogSearchCriterion);
  }

  protected setSearchValue(value: string): void {
    this.searchValue.set(value);
  }

  protected searchBooks(): void {
    const value = this.searchValue().trim();
    if (!value) {
      this.searchState.set({ status: 'error', message: 'Digite um termo para buscar.' });
      return;
    }
    this.searchState.set({ status: 'loading' });
    this.catalog
      .searchBooks(this.searchCriterion(), value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loadAvailability(data);
          this.searchState.set({ status: 'loaded', data });
        },
        error: () =>
          this.searchState.set({
            status: 'error',
            message: 'Não foi possível realizar a busca. Tente novamente.',
          }),
      });
  }

  protected availabilityFor(bookId: number): LoadState<BookAvailability> | undefined {
    return this.availability()[bookId];
  }

  private loadAvailability(books: CatalogBook[]): void {
    for (const book of books) {
      if (this.availability()[book.id]) continue;
      this.availability.update((current) => ({
        ...current,
        [book.id]: { status: 'loading' },
      }));
      this.catalog
        .getAvailability(book.id)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (data) =>
            this.availability.update((current) => ({
              ...current,
              [book.id]: { status: 'loaded', data },
            })),
          error: () =>
            this.availability.update((current) => ({
              ...current,
              [book.id]: { status: 'error', message: 'Disponibilidade indisponível.' },
            })),
        });
    }
  }

  protected clearSearch(): void {
    this.searchValue.set('');
    this.searchState.set(null);
  }

  protected isHidden(book: CatalogBook): boolean {
    return this.unfeatured().has(book.id);
  }

  // ---- Selos da vitrine (US02) --------------------------------------------

  protected offerLabel(offer: BookOffer): string {
    if (!offer.available) {
      return 'Esgotado';
    }
    return offer.destination === 'COMMERCIAL' ? 'Venda' : 'Empréstimo';
  }

  protected offerPrice(offer: BookOffer): string | null {
    if (offer.destination !== 'COMMERCIAL' || offer.price === null) {
      return null;
    }
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(Number(offer.price));
  }

  protected primaryOffer(book: CatalogBook): BookOffer | null {
    return book.offers.find((offer) => offer.available) ?? book.offers[0] ?? null;
  }

  protected actionLabel(book: CatalogBook): string {
    const offer = this.primaryOffer(book);
    if (offer === null || (!offer.available && !offer.can_reserve)) return 'Indisponível';
    if (!offer.available) return this.canServeCounter() ? 'Registrar reserva' : 'Reservar compra';
    if (this.canServeCounter()) {
      return offer.destination === 'COMMERCIAL' ? 'Registrar venda' : 'Registrar empréstimo';
    }
    return offer.destination === 'COMMERCIAL' ? 'Comprar' : 'Pedir emprestado';
  }

  protected actionDisabled(book: CatalogBook): boolean {
    const offer = this.primaryOffer(book);
    return offer === null || (!offer.available && !offer.can_reserve);
  }

  protected startTransaction(book: CatalogBook): void {
    if (!this.isAuthenticated()) {
      void this.router.navigate(['/login'], {
        queryParams: { redirectTo: this.router.url },
      });
      return;
    }
    console.info('Fluxo transacional pendente para o livro', book.id);
  }

  /** US04: gestor tira o título do destaque direto da vitrine. */
  protected removeFromFeatured(book: CatalogBook): void {
    this.featuredError.set(null);
    this.catalogAdmin
      .setBookFeatured(book.id, { is_featured: false })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          const proximo = new Set(this.unfeatured());
          proximo.add(book.id);
          this.unfeatured.set(proximo);
        },
        error: () =>
          this.featuredError.set(
            `Não foi possível remover "${book.title}" do destaque.`,
          ),
      });
  }
}
