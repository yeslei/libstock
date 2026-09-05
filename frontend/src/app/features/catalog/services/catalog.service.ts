import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { CatalogBook, Genre, PagedBooks } from '../models/catalog.model';

export const CATALOG_API = '/api/v1/catalog';

/**
 * Leitura do catálogo público. Não usa `withCredentials`: são endpoints
 * abertos, e o cookie de refresh tem `path=/api/v1/auth` — não seria enviado
 * aqui de qualquer forma.
 */
@Injectable({ providedIn: 'root' })
export class CatalogService {
  private readonly http = inject(HttpClient);

  getFeaturedBooks(): Observable<CatalogBook[]> {
    return this.http.get<CatalogBook[]>(`${CATALOG_API}/featured-books`);
  }

  getFeaturedGenres(): Observable<Genre[]> {
    return this.http.get<Genre[]>(`${CATALOG_API}/genres`);
  }

  getBooksByGenre(slug: string, page = 1): Observable<PagedBooks> {
    return this.http.get<PagedBooks>(`${CATALOG_API}/genres/${slug}/books`, {
      params: { page },
    });
  }
}
