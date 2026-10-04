import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, catchError, map, of, startWith, shareReplay } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogCapability, capabilitiesFor } from '../models/catalog-capabilities';
import { CatalogBook, Genre, LoadState } from '../models/catalog.model';
import { CatalogBookCardComponent } from '../components/catalog-book-card/catalog-book-card.component';
import { CatalogAdminService } from '../services/catalog-admin.service';
import { createAllGenresLoader } from '../services/all-genres-loader';
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
  imports: [AsyncPipe, NgTemplateOutlet, RouterLink, AlertComponent, SpinnerComponent, CatalogBookCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './catalog-home.component.html',
  styleUrl: './catalog-home.component.scss',
})
export class CatalogHomeComponent {
  private readonly catalog = inject(CatalogService);
  private readonly catalogAdmin = inject(CatalogAdminService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private searchSubscription?: Subscription;
  protected readonly allGenres = createAllGenresLoader();

  private readonly user = toSignal(this.auth.user$, { initialValue: null });

  private readonly capabilities = computed<Set<CatalogCapability>>(() =>
    capabilitiesFor(this.user()?.role_codes ?? []),
  );

  protected readonly canRegisterCopy = computed(() => this.capabilities().has('registerCopy'));

  protected readonly canManageCatalog = computed(() => this.capabilities().has('manageCatalog'));

  /** Livros retirados do destaque nesta sessão, para sumirem sem recarregar. */
  private readonly unfeatured = signal<ReadonlySet<number>>(new Set());
  protected readonly featuredError = signal<string | null>(null);

  protected readonly genres$ = this.catalog.getFeaturedGenres().pipe(
    map((data): LoadState<Genre[]> => ({ status: 'loaded', data })),
    startWith<LoadState<Genre[]>>({ status: 'loading' }),
    catchError(() =>
      of<LoadState<Genre[]>>({
        status: 'error',
        message: 'Não foi possível carregar as categorias.',
      }),
    ),
    shareReplay({ bufferSize: 1, refCount: false }),
  );

  protected readonly books$ = this.catalog.getFeaturedBooks().pipe(
    map((data): LoadState<CatalogBook[]> => ({ status: 'loaded', data })),
    startWith<LoadState<CatalogBook[]>>({ status: 'loading' }),
    catchError(() =>
      of<LoadState<CatalogBook[]>>({
        status: 'error',
        message: 'Não foi possível carregar os livros em destaque.',
      }),
    ),
    shareReplay({ bufferSize: 1, refCount: false }),
  );

  protected readonly searchCriterion = signal<CatalogSearchCriterion>('title');
  protected readonly searchValue = signal('');
  protected readonly searchState = signal<LoadState<CatalogBook[]> | null>(null);

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const q = params.get('q')?.trim() ?? '';
      this.searchSubscription?.unsubscribe();
      if (!q) { this.searchValue.set(''); this.searchState.set(null); return; }
      const criterion = params.get('criterion') ?? 'title';
      this.searchCriterion.set(['title', 'author', 'isbn', 'barcode'].includes(criterion) ? criterion as CatalogSearchCriterion : 'title');
      this.searchValue.set(q);
      this.searchBooks();
    });
  }

  protected setSearchCriterion(value: string): void {
    this.searchCriterion.set(value as CatalogSearchCriterion);
  }

  protected setSearchValue(value: string): void {
    this.searchValue.set(value);
  }

  protected searchBooks(): void {
    this.searchSubscription?.unsubscribe();
    const value = this.searchValue().trim();
    if (!value) {
      this.searchState.set({ status: 'error', message: 'Digite um termo para buscar.' });
      return;
    }
    this.searchState.set({ status: 'loading' });
    this.searchSubscription = this.catalog
      .searchBooks(this.searchCriterion(), value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => this.searchState.set({ status: 'loaded', data }),
        error: () =>
          this.searchState.set({
            status: 'error',
            message: 'Não foi possível realizar a busca. Tente novamente.',
          }),
      });
  }

  protected clearSearch(): void {
    this.searchSubscription?.unsubscribe();
    this.searchValue.set('');
    this.searchState.set(null);
    void this.router.navigate(['/'], { queryParams: {} });
  }

  protected isHidden(book: CatalogBook): boolean {
    return this.unfeatured().has(book.id);
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
