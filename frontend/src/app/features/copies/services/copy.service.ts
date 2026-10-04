import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { map, Observable } from 'rxjs';

import {
  CopyCreateRequest,
  CopyDeleteResult,
  CopyResponse,
  CopyUpdateRequest,
  copyDeleteResultFromApi,
  copyResponseFromApi,
} from '../models/copy.model';

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

  /** Edita ou converte exemplar disponível e sem operação; só os campos informados vão no corpo. */
  update(copyId: number, payload: CopyUpdateRequest): Observable<CopyResponse> {
    const body: Record<string, unknown> = {};
    if (payload.destination !== undefined) body['destination'] = payload.destination;
    if (payload.condition !== undefined) body['condition'] = payload.condition;
    if (payload.salePrice !== undefined) body['sale_price'] = payload.salePrice;
    if (payload.acquiredAt !== undefined) body['acquired_at'] = payload.acquiredAt;
    return this.http
      .patch<Parameters<typeof copyResponseFromApi>[0]>(`${COPIES_API}/${copyId}`, body)
      .pipe(map(copyResponseFromApi));
  }

  /** Exclui exemplar disponível e sem histórico; o backend decide e responde 409 com os motivos do bloqueio. */
  delete(copyId: number): Observable<CopyDeleteResult> {
    return this.http
      .delete<{ id: number; book_id: number; barcode: string }>(`${COPIES_API}/${copyId}`)
      .pipe(map(copyDeleteResultFromApi));
  }
}
