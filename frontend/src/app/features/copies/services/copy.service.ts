import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { map, Observable } from 'rxjs';

import { CopyCreateRequest, CopyResponse, copyResponseFromApi } from '../models/copy.model';

export const COPIES_API = '/api/v1/copies';

@Injectable({ providedIn: 'root' })
export class CopyService {
  private readonly http = inject(HttpClient);

  create(payload: CopyCreateRequest): Observable<CopyResponse> {
    return this.http
      .post<Parameters<typeof copyResponseFromApi>[0]>(`${COPIES_API}/`, {
        book_id: payload.bookId,
        barcode: payload.barcode,
        destination: payload.destination,
        condition: payload.condition,
        sale_price: payload.salePrice,
        acquired_at: payload.acquiredAt,
      })
      .pipe(map(copyResponseFromApi));
  }
}
