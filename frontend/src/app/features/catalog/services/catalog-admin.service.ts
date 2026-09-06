import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Genre } from '../models/catalog.model';

export const CATALOG_ADMIN_API = '/api/v1/admin';

export interface FeaturedUpdate {
  is_featured: boolean;
  position?: number | null;
}

/**
 * Operações de gestão do acervo (US04). O backend restringe a ADMINISTRATOR;
 * o token vai no header pelo `authInterceptor`, que já cobre todo caminho
 * iniciado em `/api/`.
 */
@Injectable({ providedIn: 'root' })
export class CatalogAdminService {
  private readonly http = inject(HttpClient);

  setBookFeatured(bookId: number, payload: FeaturedUpdate): Observable<unknown> {
    return this.http.patch(`${CATALOG_ADMIN_API}/books/${bookId}/featured`, payload);
  }

  setGenreFeatured(genreId: number, payload: FeaturedUpdate): Observable<Genre> {
    return this.http.patch<Genre>(`${CATALOG_ADMIN_API}/genres/${genreId}/featured`, payload);
  }
}
