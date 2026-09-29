import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { CatalogService } from '../services/catalog.service';
import { ExploreBooksComponent } from './explore-books.component';

describe('ExploreBooksComponent', () => {
  let fixture: ComponentFixture<ExploreBooksComponent>;
  let catalog: jasmine.SpyObj<CatalogService>;

  beforeEach(async () => {
    catalog = jasmine.createSpyObj<CatalogService>('CatalogService', ['searchBooks']);
    catalog.searchBooks.and.returnValue(
      of([
        {
          id: 1,
          title: 'Clean Code',
          author: 'Robert C. Martin',
          cover_url: null,
          genres: ['Tecnologia'],
          offers: [
            {
              destination: 'DIDACTIC',
              available: true,
              price: null,
              can_reserve: false,
            },
          ],
        },
      ]),
    );

    await TestBed.configureTestingModule({
      imports: [ExploreBooksComponent],
      providers: [provideRouter([]), { provide: CatalogService, useValue: catalog }],
    }).compileComponents();

    fixture = TestBed.createComponent(ExploreBooksComponent);
    fixture.detectChanges();
  });

  it('busca por título e mostra a disponibilidade do exemplar', () => {
    const root = fixture.nativeElement as HTMLElement;
    const input = root.querySelector<HTMLInputElement>('#explore-search')!;
    input.value = 'Clean Code';
    input.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('form.search')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(catalog.searchBooks).toHaveBeenCalledWith('title', 'Clean Code');
    expect(root.textContent).toContain('Clean Code');
    expect(root.textContent).toContain('Empréstimo');
  });

  it('exige um termo antes de consultar o backend', () => {
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLFormElement>('form.search')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(catalog.searchBooks).not.toHaveBeenCalled();
    expect(root.textContent).toContain('Digite um termo para buscar.');
  });
});
