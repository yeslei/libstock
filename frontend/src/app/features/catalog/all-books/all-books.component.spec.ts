import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';

import { CatalogBook, Genre, PagedCatalog } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';
import { AllBooksComponent } from './all-books.component';

const romance: Genre = { id: 1, name: 'Romance', slug: 'romance' };
const ficcao: Genre = { id: 2, name: 'Ficção', slug: 'ficcao' };

function book(id: number, title: string, available: boolean): CatalogBook {
  return {
    id, title, author: 'Autora', cover_url: null, genres: ['Romance'],
    offers: [{ destination: 'DIDACTIC', available, price: null, can_reserve: false }],
  };
}

function page(items: CatalogBook[], total = items.length, current = 1): PagedCatalog {
  return { items, total, page: current, page_size: 12 };
}

describe('AllBooksComponent (/acervo)', () => {
  let fixture: ComponentFixture<AllBooksComponent>;
  let root: HTMLElement;
  let allBooks: jasmine.Spy;
  let allGenres: jasmine.Spy;
  let router: Router;
  const query = new BehaviorSubject(convertToParamMap({}));

  async function create(response: unknown = of(page([book(1, 'Orgulho e Preconceito', true), book(2, 'Jane Eyre', false)])), params = {}) {
    query.next(convertToParamMap(params));
    allBooks = jasmine.createSpy('getAllBooks').and.returnValue(response);
    allGenres = jasmine.createSpy('getAllGenres').and.returnValue(of([ficcao, romance, { id: 3, name: 'Poesia', slug: 'poesia' }]));
    await TestBed.configureTestingModule({
      imports: [AllBooksComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { queryParamMap: query } },
        { provide: CatalogService, useValue: { getAllBooks: allBooks, getFeaturedGenres: () => of([ficcao, romance]), getAllGenres: allGenres } },
      ],
    }).compileComponents();
    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);
    fixture = TestBed.createComponent(AllBooksComponent);
    fixture.detectChanges();
    root = fixture.nativeElement as HTMLElement;
  }

  function submit(term: string): void {
    const input = root.querySelector<HTMLInputElement>('#all-books-search')!;
    input.value = term;
    input.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('form.genre__search')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('lista o acervo com disponibilidade, chips "Todos" ativo e "Mais"', async () => {
    await create();
    expect(root.querySelector('h1')!.textContent).toBe('Acervo completo');
    expect(allBooks).toHaveBeenCalledWith(1, '');
    expect(root.querySelectorAll('app-catalog-book-card').length).toBe(2);
    expect(root.textContent).toContain('Empréstimo disponível');
    expect(root.textContent).toContain('Esgotado');
    expect(root.textContent).toContain('2 livro(s)');
    const chips = Array.from(root.querySelectorAll('.genre__chip')).map((c) => c.textContent!.trim());
    expect(chips).toEqual(['Todos', 'Ficção', 'Romance', 'Mais']);
    expect(root.querySelector('.genre__chip--active')!.textContent).toContain('Todos');
    expect(root.querySelector('a[href="/generos/romance"]')).not.toBeNull();
  });

  it('"Mais" mostra todas as categorias', async () => {
    await create();
    root.querySelector<HTMLButtonElement>('button.genre__chip--more')!.click();
    fixture.detectChanges();
    expect(Array.from(root.querySelectorAll('.genre__chip')).map((c) => c.textContent!.trim())).toEqual(['Todos', 'Ficção', 'Romance', 'Poesia', 'Menos']);
    expect(allGenres).toHaveBeenCalledTimes(1);
  });

  it('lê página e termo da URL', async () => {
    await create(of(page([book(1, 'Dom Casmurro', true)], 30, 2)), { page: '2', q: ' dom ' });
    expect(allBooks).toHaveBeenCalledWith(2, 'dom');
    expect(root.querySelector<HTMLInputElement>('#all-books-search')!.value).toBe('dom');
    expect(root.textContent).toContain('Página 2 de 3');
  });

  it('ignora página inválida na URL', async () => {
    await create(of(page([])), { page: 'abc' });
    expect(allBooks).toHaveBeenCalledWith(1, '');
  });

  it('busca navegando com q e sem página', async () => {
    await create();
    submit('  jane ');
    expect(router.navigate).toHaveBeenCalledWith([], { queryParams: { q: 'jane', page: null }, queryParamsHandling: 'merge' });
  });

  it('pagina pela URL', async () => {
    await create(of(page([book(1, 'A', true)], 30, 1)));
    const [previous, next] = Array.from(root.querySelectorAll<HTMLButtonElement>('.genre__pager button'));
    expect(previous.disabled).toBeTrue();
    next.click();
    expect(router.navigate).toHaveBeenCalledWith([], { queryParams: { page: 2 }, queryParamsHandling: 'merge' });
  });

  it('não mostra paginação com uma página só', async () => {
    await create();
    expect(root.querySelector('.genre__pager')).toBeNull();
  });

  it('exibe carregamento, erro, acervo vazio e nenhum resultado com "Limpar busca"', async () => {
    await create(new Subject<PagedCatalog>());
    expect(root.textContent).toContain('Carregando');
    TestBed.resetTestingModule();
    await create(throwError(() => ({ status: 500 })));
    expect(root.textContent).toContain('Não foi possível carregar o acervo.');
    TestBed.resetTestingModule();
    await create(of(page([])));
    expect(root.textContent).toContain('Nenhum livro no acervo no momento.');
    TestBed.resetTestingModule();
    await create(of(page([])), { q: 'zzz' });
    expect(root.textContent).toContain('Nenhum livro encontrado para “zzz”.');
    root.querySelector<HTMLButtonElement>('.genre__clear')!.click();
    expect(router.navigate).toHaveBeenCalledWith([], { queryParams: { q: null, page: null }, queryParamsHandling: 'merge' });
  });
});
