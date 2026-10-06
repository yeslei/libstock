import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, map, of, startWith, switchMap } from 'rxjs';

import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { LoadState, PagedBooks } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';

/**
 * Listagem de um gênero. Entrega mínima de propósito: o filtro rico e a
 * paginação completa pertencem à frente de busca, que está sendo feita em
 * paralelo. O que precisa estar de pé aqui é a navegação a partir do chip.
 */
@Component({
  selector: 'app-genre-books',
  standalone: true,
  imports: [AsyncPipe, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './genre-books.component.html',
  styleUrl: './genre-books.component.scss',
})
export class GenreBooksComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly catalog = inject(CatalogService);

  private readonly slug$ = this.route.paramMap.pipe(map((params) => params.get('slug') ?? ''));

  protected readonly books$ = this.slug$.pipe(
    switchMap((slug) =>
      this.catalog.getBooksByGenre(slug).pipe(
        map((data): LoadState<PagedBooks> => ({ status: 'loaded', data })),
        startWith<LoadState<PagedBooks>>({ status: 'loading' }),
        catchError((error: { status?: number }) =>
          of<LoadState<PagedBooks>>({
            status: 'error',
            message:
              error.status === 404
                ? 'Categoria não encontrada.'
                : 'Não foi possível carregar os livros desta categoria.',
          }),
        ),
      ),
    ),
  );
}
