import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { BookCreateRequest, BookDetail, BookMetadata, BookResponse, BookUpdateRequest } from '../models/book.model';

export const BOOKS_API = '/api/v1/books';

@Injectable({ providedIn: 'root' })
export class BookService {
  private readonly http = inject(HttpClient);

  create(payload: BookCreateRequest): Observable<BookResponse> {
    return this.http.post<BookResponse>(`${BOOKS_API}/`, payload);
  }

  lookupMetadata(isbn: string): Observable<BookMetadata> {
    return this.http.get<BookMetadata>(`${BOOKS_API}/metadata/${encodeURIComponent(isbn)}`);
  }

  get(bookId: number): Observable<BookDetail> {
    return this.http.get<BookDetail>(`${BOOKS_API}/${bookId}`);
  }

  update(bookId: number, payload: BookUpdateRequest): Observable<BookDetail> {
    return this.http.patch<BookDetail>(`${BOOKS_API}/${bookId}`, payload);
  }
}
