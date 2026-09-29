import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { BookCreateRequest, BookResponse, BookUpdateRequest } from '../models/book.model';

export const BOOKS_API = '/api/v1/books';
export const ACERVO_API = '/api/v1/acervo';

@Injectable({ providedIn: 'root' })
export class BookService {
  private readonly http = inject(HttpClient);

  create(payload: BookCreateRequest): Observable<BookResponse> {
    return this.http.post<BookResponse>(`${BOOKS_API}/`, payload);
  }

  update(id: number, payload: BookUpdateRequest): Observable<BookResponse> {
    return this.http.patch<BookResponse>(`${ACERVO_API}/${id}`, payload);
  }
}
