import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { catchError, map, of, startWith } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { BookOffer, CatalogBook, Genre, LoadState } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';

/**
 * Vitrine pública. Qualquer visitante navega sem sessão; o login só é exigido
 * nas ações transacionais (comprar / pedir emprestado).
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
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly isAuthenticated$ = this.auth.isAuthenticated$;

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

  protected offerLabel(offer: BookOffer): string {
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

  /**
   * Ação transacional exige sessão. Sem ela, manda para o login preservando o
   * destino — mesmo contrato de `redirectTo` que o `authGuard` usa.
   */
  protected startTransaction(book: CatalogBook): void {
    if (!this.auth.currentUser) {
      void this.router.navigate(['/login'], {
        queryParams: { redirectTo: this.router.url },
      });
      return;
    }
    // TODO: fluxo de compra/empréstimo — fora do escopo desta entrega.
    console.info('Fluxo transacional pendente para o livro', book.id);
  }
}
