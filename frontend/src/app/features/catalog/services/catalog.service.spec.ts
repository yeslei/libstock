import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CATALOG_API, CatalogService } from './catalog.service';

describe('CatalogService', () => {
  let service: CatalogService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(CatalogService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista a categoria sem enviar termo quando a busca está vazia', () => {
    service.getBooksByGenre('romance', 2, '  ').subscribe();
    const req = http.expectOne((r) => r.url === `${CATALOG_API}/genres/romance/books`);
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.has('q')).toBeFalse();
    req.flush({});
  });

  it('pede todas as categorias, não só as em destaque', () => {
    service.getAllGenres().subscribe();
    const req = http.expectOne((r) => r.url === `${CATALOG_API}/genres`);
    expect(req.request.params.get('all')).toBe('true');
    req.flush([]);
  });

  it('lista o acervo completo paginado, com termo aparado só quando houver', () => {
    service.getAllBooks(3, '  dom ').subscribe();
    let req = http.expectOne((r) => r.url === `${CATALOG_API}/books/all`);
    expect(req.request.params.get('page')).toBe('3');
    expect(req.request.params.get('page_size')).toBe('12');
    expect(req.request.params.get('q')).toBe('dom');
    req.flush({});
    service.getAllBooks().subscribe();
    req = http.expectOne((r) => r.url === `${CATALOG_API}/books/all`);
    expect(req.request.params.get('page')).toBe('1');
    expect(req.request.params.has('q')).toBeFalse();
    req.flush({});
  });

  it('envia o termo aparado para buscar dentro da categoria', () => {
    service.getBooksByGenre('romance', 1, ' Jane ').subscribe();
    const req = http.expectOne((r) => r.url === `${CATALOG_API}/genres/romance/books`);
    expect(req.request.params.get('q')).toBe('Jane');
    req.flush({});
  });
});
