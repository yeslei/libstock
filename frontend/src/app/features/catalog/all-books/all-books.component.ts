import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable, catchError, map, of, startWith, switchMap } from 'rxjs';

import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogBookCardComponent } from '../components/catalog-book-card/catalog-book-card.component';
import { Genre, PagedCatalog } from '../models/catalog.model';
import { createAllGenresLoader } from '../services/all-genres-loader';
import { CatalogService } from '../services/catalog.service';

interface AllBooksView {
  readonly status: 'loading' | 'loaded' | 'error';
  readonly data?: PagedCatalog;
  readonly message?: string;
}

/**
 * Acervo completo (rota `/acervo`): "Ver todos" dos destaques e "Todos" dos
 * chips. Página e termo ficam na URL (`?page=&q=`), então voltar, recarregar
 * e compartilhar o link preservam a consulta.
 */
@Component({
  selector: 'app-all-books',
  standalone: true,
  imports: [AsyncPipe, RouterLink, AlertComponent, SpinnerComponent, CatalogBookCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './all-books.component.html',
  // Mesmo visual da listagem por categoria.
  styleUrl: '../genre-books/genre-books.component.scss',
})
export class AllBooksComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly catalog = inject(CatalogService);
  protected readonly allGenres = createAllGenresLoader();

  /** Texto digitado; só vira consulta ao enviar (Enter ou "Buscar"). */
  protected readonly term = signal('');
  /** Termo da consulta em andamento, para a mensagem de resultado vazio. */
  protected readonly activeQuery = signal('');

  protected readonly genres$: Observable<Genre[]> = this.catalog
    .getFeaturedGenres()
    .pipe(catchError(() => of<Genre[]>([])));

  protected readonly state$: Observable<AllBooksView> = this.route.queryParamMap.pipe(
    map((params) => {
      const page = Number(params.get('page'));
      return {
        q: (params.get('q') ?? '').trim().slice(0, 100),
        page: Number.isSafeInteger(page) && page >= 1 ? page : 1,
      };
    }),
    switchMap(({ q, page }) => {
      this.term.set(q);
      this.activeQuery.set(q);
      return this.catalog.getAllBooks(page, q).pipe(
        map((data): AllBooksView => ({ status: 'loaded', data })),
        startWith<AllBooksView>({ status: 'loading' }),
        catchError(() =>
          of<AllBooksView>({ status: 'error', message: 'Não foi possível carregar o acervo.' }),
        ),
      );
    }),
  );

  protected setTerm(value: string): void {
    this.term.set(value);
  }

  protected search(): void {
    const q = this.term().trim();
    void this.router.navigate([], { queryParams: { q: q || null, page: null }, queryParamsHandling: 'merge' });
  }

  protected clearSearch(): void {
    this.term.set('');
    this.search();
  }

  protected goToPage(page: number): void {
    void this.router.navigate([], { queryParams: { page: page > 1 ? page : null }, queryParamsHandling: 'merge' });
  }

  protected totalPages(data: PagedCatalog): number {
    return Math.max(1, Math.ceil(data.total / data.page_size));
  }
}
