import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { BehaviorSubject, Observable, catchError, map, of, startWith, switchMap, tap } from 'rxjs';

import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { CatalogBookCardComponent } from '../components/catalog-book-card/catalog-book-card.component';
import { Genre, PagedBooks } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';

interface GenreView {
  readonly status: 'loading' | 'loaded' | 'error';
  /** Última categoria conhecida: mantém título, busca e filtros enquanto a lista recarrega. */
  readonly genre: Genre | null;
  readonly data?: PagedBooks;
  readonly message?: string;
}

/**
 * Listagem de uma categoria, conforme "Ao selecionar uma categoria" (Figma):
 * trilha, título, busca dentro da categoria, chips das categorias em destaque
 * (navegação entre categorias) e cartões com a disponibilidade real.
 */
@Component({
  selector: 'app-genre-books',
  standalone: true,
  imports: [AsyncPipe, RouterLink, AlertComponent, SpinnerComponent, CatalogBookCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './genre-books.component.html',
  styleUrl: './genre-books.component.scss',
})
export class GenreBooksComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly catalog = inject(CatalogService);

  private readonly slug$ = this.route.paramMap.pipe(map((params) => params.get('slug') ?? ''));
  private readonly view$ = new BehaviorSubject<{ q: string; page: number }>({ q: '', page: 1 });
  private knownGenre: Genre | null = null;

  /** Texto digitado; só vira consulta ao enviar (Enter ou "Buscar"). */
  protected readonly term = signal('');
  /** Termo da consulta em andamento, para a mensagem de resultado vazio. */
  protected readonly activeQuery = signal('');

  protected readonly genres$: Observable<Genre[]> = this.catalog
    .getFeaturedGenres()
    .pipe(catchError(() => of<Genre[]>([])));

  protected readonly state$: Observable<GenreView> = this.slug$.pipe(
    tap(() => {
      this.knownGenre = null;
      this.term.set('');
      this.activeQuery.set('');
      this.view$.next({ q: '', page: 1 });
    }),
    switchMap((slug) =>
      this.view$.pipe(
        switchMap(({ q, page }) =>
          this.catalog.getBooksByGenre(slug, page, q).pipe(
            map((data): GenreView => {
              this.knownGenre = data.genre;
              return { status: 'loaded', genre: data.genre, data };
            }),
            startWith<GenreView>({ status: 'loading', genre: this.knownGenre }),
            catchError((error: { status?: number }) =>
              of<GenreView>({
                status: 'error',
                genre: this.knownGenre,
                message:
                  error.status === 404
                    ? 'Categoria não encontrada.'
                    : 'Não foi possível carregar os livros desta categoria.',
              }),
            ),
          ),
        ),
      ),
    ),
  );

  protected setTerm(value: string): void {
    this.term.set(value);
  }

  protected search(): void {
    const q = this.term().trim();
    this.activeQuery.set(q);
    this.view$.next({ q, page: 1 });
  }

  protected clearSearch(): void {
    this.term.set('');
    this.search();
  }

  protected goToPage(page: number): void {
    this.view$.next({ q: this.view$.value.q, page });
  }

  protected totalPages(data: PagedBooks): number {
    return Math.max(1, Math.ceil(data.total / data.page_size));
  }
}
