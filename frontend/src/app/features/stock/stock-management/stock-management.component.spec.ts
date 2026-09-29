import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { BookService } from '../../books/services/book.service';
import { CatalogService } from '../../catalog/services/catalog.service';
import { StockManagementComponent } from './stock-management.component';

describe('StockManagementComponent', () => {
  let fixture: ComponentFixture<StockManagementComponent>;
  let catalog: jasmine.SpyObj<CatalogService>;
  let books: jasmine.SpyObj<BookService>;

  beforeEach(async () => {
    catalog = jasmine.createSpyObj('CatalogService', ['searchBooks']);
    books = jasmine.createSpyObj('BookService', ['get']);
    catalog.searchBooks.and.returnValue(of([{ id: 7, title: 'Obra', author: 'Autora', cover_url: null, genres: [], offers: [] }]));
    books.get.and.returnValue(of({ id: 7, isbn: '9788575225530', title: 'Obra', author: 'Autora', genre: null, cover_url: null, is_active: true, initial_copy: null, copies: [] }));
    await TestBed.configureTestingModule({ imports: [StockManagementComponent], providers: [provideRouter([]), { provide: CatalogService, useValue: catalog }, { provide: BookService, useValue: books }] }).compileComponents();
    fixture = TestBed.createComponent(StockManagementComponent);
    fixture.detectChanges();
  });

  it('pesquisa, seleciona e oferece edição ou novo exemplar', () => {
    const root = fixture.nativeElement as HTMLElement;
    const input = root.querySelector<HTMLInputElement>('#stock-term')!;
    input.value = 'Obra'; input.dispatchEvent(new Event('input'));
    root.querySelector('form')!.dispatchEvent(new Event('submit')); fixture.detectChanges();
    root.querySelector<HTMLButtonElement>('.results button')!.click(); fixture.detectChanges();
    expect(catalog.searchBooks).toHaveBeenCalledWith('title', 'Obra');
    expect(books.get).toHaveBeenCalledWith(7);
    expect(root.querySelector('a[href="/gestao/acervo/obras/7/editar"]')).not.toBeNull();
    expect(root.querySelector('a[href="/obras/7/exemplares/novo"]')).not.toBeNull();
  });

  it('não consulta com termo vazio', () => {
    (fixture.nativeElement as HTMLElement).querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(catalog.searchBooks).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Digite um termo');
  });
});
