import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';

import { CatalogBook, Genre, PagedBooks } from '../models/catalog.model';
import { CatalogService } from '../services/catalog.service';
import { GenreBooksComponent } from './genre-books.component';

const romance: Genre = { id: 1, name: 'Romance', slug: 'romance' };
const ficcao: Genre = { id: 2, name: 'Ficção', slug: 'ficcao' };

function book(id: number, title: string, available: boolean): CatalogBook {
  return {
    id, title, author: 'Autora', cover_url: null, genres: ['Romance'],
    offers: [{ destination: 'DIDACTIC', available, price: null, can_reserve: false }],
  };
}

function page(items: CatalogBook[], total = items.length, current = 1): PagedBooks {
  return { genre: romance, items, total, page: current, page_size: 12 };
}

describe('GenreBooksComponent', () => {
  let fixture: ComponentFixture<GenreBooksComponent>;
  let root: HTMLElement;
  let byGenre: jasmine.Spy;
  let allGenres: jasmine.Spy;
  const params = new BehaviorSubject(convertToParamMap({ slug: 'romance' }));

  async function create(response: unknown = of(page([book(1, 'Orgulho e Preconceito', true), book(2, 'Jane Eyre', false)]))) {
    params.next(convertToParamMap({ slug: 'romance' }));
    byGenre = jasmine.createSpy('getBooksByGenre').and.returnValue(response);
    allGenres = jasmine.createSpy('getAllGenres').and.returnValue(of([ficcao, romance, { id: 3, name: 'Poesia', slug: 'poesia' }]));
    await TestBed.configureTestingModule({
      imports: [GenreBooksComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: params } },
        { provide: CatalogService, useValue: { getBooksByGenre: byGenre, getFeaturedGenres: () => of([ficcao, romance]), getAllGenres: allGenres } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(GenreBooksComponent);
    fixture.detectChanges();
    root = fixture.nativeElement as HTMLElement;
  }

  function submit(term: string): void {
    const input = root.querySelector<HTMLInputElement>('#genre-search')!;
    input.value = term;
    input.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('form.genre__search')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('mostra trilha, título, busca, chips e cartões com a disponibilidade real', async () => {
    await create();
    expect(root.querySelector('.genre__crumbs')!.textContent).toContain('Explorar acervo');
    expect(root.querySelector('h1')!.textContent).toBe('Romance');
    expect(root.textContent).toContain('Livros filtrados pela categoria Romance.');
    expect(root.querySelector<HTMLInputElement>('#genre-search')!.placeholder).toBe('Buscar dentro de Romance');
    const chips = Array.from(root.querySelectorAll('.genre__chip')).map((c) => c.textContent!.trim());
    expect(chips).toEqual(['Todos', 'Ficção', 'Romance', 'Mais']);
    expect(root.querySelector('a.genre__chip[href="/acervo"]')!.textContent).toContain('Todos');
    expect(root.querySelector('.genre__crumbs a')!.getAttribute('href')).toBe('/acervo');
    expect(root.querySelector('.genre__chip--active')!.textContent).toContain('Romance');
    expect(root.querySelector('.genre__chip--active')!.getAttribute('aria-current')).toBe('page');
    expect(root.querySelectorAll('app-catalog-book-card').length).toBe(2);
    expect(root.textContent).toContain('Empréstimo disponível');
    expect(root.textContent).toContain('Esgotado');
    expect(byGenre).toHaveBeenCalledWith('romance', 1, '');
  });

  it('"Mais" troca os destaques pela lista completa de categorias, uma única consulta', async () => {
    await create();
    const more = () => Array.from(root.querySelectorAll<HTMLButtonElement>('button.genre__chip--more'))[0];
    expect(allGenres).not.toHaveBeenCalled();
    more().click(); fixture.detectChanges();
    const names = () => Array.from(root.querySelectorAll('.genre__chip')).map((c) => c.textContent!.trim());
    expect(names()).toEqual(['Todos', 'Ficção', 'Romance', 'Poesia', 'Menos']);
    more().click(); fixture.detectChanges();
    expect(names()).toEqual(['Todos', 'Ficção', 'Romance', 'Mais']);
    more().click(); fixture.detectChanges();
    expect(allGenres).toHaveBeenCalledTimes(1);
  });

  it('mantém os destaques e avisa quando a lista completa falha', async () => {
    await create();
    allGenres.and.returnValue(throwError(() => ({ status: 500 })));
    root.querySelector<HTMLButtonElement>('button.genre__chip--more')!.click();
    fixture.detectChanges();
    expect(root.textContent).toContain('Não foi possível carregar todas as categorias.');
    expect(Array.from(root.querySelectorAll('.genre__chip')).map((c) => c.textContent!.trim())).toEqual(['Todos', 'Ficção', 'Romance', 'Mais']);
  });

  it('exibe o estado de carregamento', async () => {
    await create(new Subject<PagedBooks>());
    expect(root.textContent).toContain('Carregando');
    expect(root.querySelector('app-catalog-book-card')).toBeNull();
  });

  it('informa categoria inexistente e erro genérico', async () => {
    await create(throwError(() => ({ status: 404 })));
    expect(root.textContent).toContain('Categoria não encontrada.');
    expect(root.querySelector('a[href="/"]')).not.toBeNull();
  });

  it('informa falha ao carregar a categoria', async () => {
    await create(throwError(() => ({ status: 500 })));
    expect(root.textContent).toContain('Não foi possível carregar os livros desta categoria.');
  });

  it('informa categoria vazia', async () => {
    await create(of(page([])));
    expect(root.textContent).toContain('Nenhum livro disponível nesta categoria.');
  });

  it('busca dentro da categoria e permite limpar a busca', async () => {
    await create();
    byGenre.and.returnValue(of(page([])));
    submit('  jane ');
    expect(byGenre).toHaveBeenCalledWith('romance', 1, 'jane');
    expect(root.textContent).toContain('Nenhum livro encontrado para “jane” em Romance.');

    byGenre.and.returnValue(of(page([book(1, 'Orgulho e Preconceito', true)])));
    root.querySelector<HTMLButtonElement>('.genre__clear')!.click();
    fixture.detectChanges();
    expect(byGenre).toHaveBeenCalledWith('romance', 1, '');
    expect(root.querySelector<HTMLInputElement>('#genre-search')!.value).toBe('');
    expect(root.querySelectorAll('app-catalog-book-card').length).toBe(1);
  });

  it('mantém a busca e o foco enquanto a lista recarrega', async () => {
    await create();
    const pending = new Subject<PagedBooks>();
    byGenre.and.returnValue(pending);
    submit('jane');
    expect(root.querySelector('#genre-search')).not.toBeNull();
    expect(root.textContent).toContain('Carregando');
    pending.next(page([book(2, 'Jane Eyre', false)]));
    fixture.detectChanges();
    expect(root.querySelectorAll('app-catalog-book-card').length).toBe(1);
  });

  it('pagina quando há mais de uma página', async () => {
    await create(of(page([book(1, 'A', true)], 30, 1)));
    expect(root.textContent).toContain('Página 1 de 3');
    const [previous, next] = Array.from(root.querySelectorAll<HTMLButtonElement>('.genre__pager button'));
    expect(previous.disabled).toBeTrue();
    byGenre.and.returnValue(of(page([book(2, 'B', true)], 30, 2)));
    next.click();
    fixture.detectChanges();
    expect(byGenre).toHaveBeenCalledWith('romance', 2, '');
  });

  it('volta à primeira página e zera a busca ao trocar de categoria', async () => {
    await create();
    submit('jane');
    byGenre.and.returnValue(of({ ...page([book(3, 'Dune', true)]), genre: ficcao }));
    params.next(convertToParamMap({ slug: 'ficcao' }));
    fixture.detectChanges();
    expect(byGenre).toHaveBeenCalledWith('ficcao', 1, '');
    expect(root.querySelector<HTMLInputElement>('#genre-search')!.value).toBe('');
    expect(root.querySelector('h1')!.textContent).toBe('Ficção');
  });
});
