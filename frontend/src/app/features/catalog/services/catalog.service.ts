import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { BookAvailability, CatalogBook, CatalogBookDetail, Genre, PagedBooks, PagedCatalog } from '../models/catalog.model';

export const CATALOG_API = '/api/v1/catalog';
export type CatalogSearchCriterion = 'title' | 'author' | 'isbn' | 'barcode';

/**
 * Leitura do catálogo público. Não usa `withCredentials`: são endpoints
 * abertos, e o cookie de refresh tem `path=/api/v1/auth` — não seria enviado
 * aqui de qualquer forma.
 */
@Injectable({ providedIn: 'root' })
export class CatalogService {
  private readonly http = inject(HttpClient);

  getBook(id: number): Observable<CatalogBookDetail> {
    return this.http.get<CatalogBookDetail>(`${CATALOG_API}/books/${id}`);
  }

  getFeaturedBooks(): Observable<CatalogBook[]> {
    return this.http.get<CatalogBook[]>(`${CATALOG_API}/featured-books`);
  }

  getFeaturedGenres(): Observable<Genre[]> {
    return this.http.get<Genre[]>(`${CATALOG_API}/genres`);
  }

  /** Todas as categorias, inclusive as fora de destaque (chip "Mais"). */
  getAllGenres(): Observable<Genre[]> {
    return this.http.get<Genre[]>(`${CATALOG_API}/genres`, { params: { all: true } });
  }

  /** Acervo público completo, paginado, com busca opcional por título ou autor. */
  getAllBooks(page = 1, q = '', pageSize = 12): Observable<PagedCatalog> {
    const term = q.trim();
    return this.http.get<PagedCatalog>(`${CATALOG_API}/books/all`, {
      params: term ? { page, page_size: pageSize, q: term } : { page, page_size: pageSize },
    });
  }

  getBooksByGenre(slug: string, page = 1, q = ''): Observable<PagedBooks> {
    const term = q.trim();
    return this.http.get<PagedBooks>(`${CATALOG_API}/genres/${slug}/books`, {
      params: term ? { page, q: term } : { page },
    });
  }

  searchBooks(criterion: CatalogSearchCriterion, value: string): Observable<CatalogBook[]> {
    return this.http.get<CatalogBook[]>(`${CATALOG_API}/books`, {
      params: { [criterion]: value },
    });
  }

  getAvailability(bookId: number): Observable<BookAvailability> {
    return this.http.get<BookAvailability>(`/api/v1/books/${bookId}/availability`);
  }
}
