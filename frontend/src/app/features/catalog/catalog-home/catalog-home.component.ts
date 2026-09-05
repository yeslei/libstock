import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { catchError, map, of, startWith } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogCapability, capabilitiesFor } from '../models/catalog-capabilities';
import { BookOffer, CatalogBook, Genre, LoadState } from '../models/catalog.model';
import { CatalogAdminService } from '../services/catalog-admin.service';
import { CatalogService } from '../services/catalog.service';

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
  imports: [AsyncPipe, RouterLink, AlertComponent, SpinnerComponent],
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

  protected readonly isAuthenticated = computed(() => this.user() !== null);

  private readonly capabilities = computed<Set<CatalogCapability>>(() =>
    capabilitiesFor(this.user()?.role_codes ?? []),
  );

  protected readonly canManageCatalog = computed(() => this.capabilities().has('manageCatalog'));
  protected readonly canServeCounter = computed(() => this.capabilities().has('counterService'));
  protected readonly canManageStock = computed(() => this.capabilities().has('manageStock'));

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
  );

  /** A busca é de outra frente de trabalho; o campo fica visível e inerte. */
  protected readonly searchDisabled = signal(true);

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

  /** Oferta que comanda o botão do card: a disponível vence a esgotada. */
  protected primaryOffer(book: CatalogBook): BookOffer | null {
    return book.offers.find((offer) => offer.available) ?? book.offers[0] ?? null;
  }

  /**
   * A disponibilidade manda antes do papel: não há venda nem empréstimo a
   * registrar sem exemplar livre, por mais privilegiado que seja quem opera.
   * Um exemplar vendido é estado final da máquina de estados de `Copy`.
   */
  protected actionLabel(book: CatalogBook): string {
    const offer = this.primaryOffer(book);
    if (offer === null) {
      return 'Indisponível';
    }

    if (!offer.available) {
      if (!offer.can_reserve) {
        return 'Indisponível';
      }
      // RF07: o balcão pode registrar a reserva em nome do cliente (US01).
      return this.canServeCounter() ? 'Registrar reserva' : 'Reservar compra';
    }

    if (this.canServeCounter()) {
      return offer.destination === 'COMMERCIAL' ? 'Registrar venda' : 'Registrar empréstimo';
    }
    return offer.destination === 'COMMERCIAL' ? 'Comprar' : 'Pedir emprestado';
  }

  protected actionDisabled(book: CatalogBook): boolean {
    const offer = this.primaryOffer(book);
    if (offer === null) {
      return true;
    }
    // Esgotado sem direito a reserva não tem ação possível — RF07 só cobre
    // exemplar de venda que está emprestado, não o que já foi vendido.
    return !offer.available && !offer.can_reserve;
  }

  // ---- Ações --------------------------------------------------------------

  /**
   * Ação transacional exige sessão. Sem ela, manda para o login preservando o
   * destino — mesmo contrato de `redirectTo` que o `authGuard` usa.
   */
  protected startTransaction(book: CatalogBook): void {
    if (!this.isAuthenticated()) {
      void this.router.navigate(['/login'], {
        queryParams: { redirectTo: this.router.url },
      });
      return;
    }
    // TODO(RF02/RF03/RF07): venda, empréstimo e reserva ainda não têm
    // endpoint. O gate de sessão acima já é o comportamento definitivo.
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
