import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { BookCreateRequest, BookResponse } from '../models/book.model';
import { BOOKS_API, BookService } from './book.service';

describe('BookService', () => {
  let service: BookService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(BookService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('usa a URL relativa configurada e o endpoint correto', () => {
    const payload: BookCreateRequest = {
      isbn: '9788575225530', title: null, author: null, genre: null,
      initial_copy: { barcode: 'EX-1', destination: 'DIDACTIC', condition: null, sale_price: null, acquired_at: null },
    };
    const response: BookResponse = {
      id: 1, isbn: payload.isbn, title: 'Título', author: 'Autor', genre: null, is_active: true,
      initial_copy: { id: 2, book_id: 1, is_active: true, status: 'AVAILABLE', ...payload.initial_copy },
    };

    service.create(payload).subscribe((book) => expect(book).toEqual(response));

    const request = http.expectOne(`${BOOKS_API}/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    request.flush(response, { status: 201, statusText: 'Created' });
  });
});
