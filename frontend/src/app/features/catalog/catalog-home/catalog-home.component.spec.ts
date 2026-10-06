import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';
import { User } from '../../../core/models/user.model';
import { CatalogBook } from '../models/catalog.model';

import { AuthService } from '../../../core/services/auth.service';
import { CatalogAdminService } from '../services/catalog-admin.service';
import { CatalogService } from '../services/catalog.service';
import { CatalogHomeComponent } from './catalog-home.component';

describe('CatalogHomeComponent', () => {
  let fixture: ComponentFixture<CatalogHomeComponent>;
  const params = new BehaviorSubject(convertToParamMap({}));
  let search: jasmine.Spy;
  let user$: BehaviorSubject<User>;

  beforeEach(async () => {
    params.next(convertToParamMap({}));
    search = jasmine.createSpy('searchBooks').and.returnValue(of([]));
    user$ = new BehaviorSubject<User>({
      id: 1, name: 'Vendedora', email: 'vendedora@teste.dev', role_codes: ['SELLER' as const], created_at: '2026-09-06',
    });
    await TestBed.configureTestingModule({
      imports: [CatalogHomeComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { queryParamMap: params } },
        { provide: AuthService, useValue: { user$ } },
        { provide: CatalogAdminService, useValue: { setBookFeatured: () => of(void 0) } },
        {
          provide: CatalogService,
          useValue: {
            getFeaturedGenres: () => of([]),
            getFeaturedBooks: () => of([{
              id: 42, title: 'Obra de teste', author: 'Autor', genres: [], cover_url: null, offers: [],
            }]),
            searchBooks: search,
          },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CatalogHomeComponent);
    fixture.detectChanges();
  });

  it('não repete o cadastro de exemplar nos cards', () => {
    expect(fixture.nativeElement.textContent).not.toContain('Cadastrar exemplar');
  });

  it('não oferece cadastro de exemplar nos cards nem para o estoquista: ele passou para o balcão', () => {
    user$.next({ ...user$.value, role_codes: ['STOCK_KEEPER'] });
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).not.toContain('Cadastrar exemplar');
    expect(root.querySelector('a[href="/obras/42/exemplares/novo"]')).toBeNull();
    expect(root.querySelector('a[href="/livros/42"]')).not.toBeNull();
  });

  it('exibe apenas os resultados enquanto houver uma busca ativa', () => {
    const root = fixture.nativeElement as HTMLElement;
    const input = root.querySelector<HTMLInputElement>('#catalog-search')!;
    input.value = 'obra';
    input.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('form.search')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(root.textContent).toContain('Resultado da busca');
    expect(root.textContent).not.toContain('Categorias em destaque');
    expect(root.textContent).not.toContain('Livros em destaque');

    root.querySelector<HTMLButtonElement>('button.btn--outline')!.click();
    fixture.detectChanges();

    expect(root.textContent).toContain('Categorias em destaque');
    expect(root.textContent).toContain('Livros em destaque');
    expect(input.value).toBe('');
  });

  it('usa a busca do header e descarta a resposta do termo anterior', () => {
    const first = new Subject<CatalogBook[]>();
    const second = new Subject<CatalogBook[]>();
    search.and.returnValues(first, second);
    params.next(convertToParamMap({ q: 'Machado', criterion: 'author' }));
    expect(search).toHaveBeenCalledWith('author', 'Machado');
    params.next(convertToParamMap({ q: '1984', criterion: 'unknown' }));
    expect(search).toHaveBeenCalledWith('title', '1984');
    second.next([]);
    first.next([{ id: 1, title: 'Resultado antigo', author: '', cover_url: null, genres: [], offers: [] }]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Resultado antigo');
    expect(fixture.nativeElement.textContent).toContain('Nenhum livro encontrado');
  });
});

describe('CatalogHomeComponent (conteúdo da referência)', () => {
  let current: ComponentFixture<CatalogHomeComponent>;
  async function render(genres: unknown, books: unknown): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [CatalogHomeComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { queryParamMap: new BehaviorSubject(convertToParamMap({})) } },
        { provide: AuthService, useValue: { user$: new BehaviorSubject<User | null>(null) } },
        { provide: CatalogAdminService, useValue: { setBookFeatured: () => of(void 0) } },
        { provide: CatalogService, useValue: { getFeaturedGenres: () => genres, getFeaturedBooks: () => books, searchBooks: () => of([]), getAllGenres: () => of([{ id: 1, name: 'Romance', slug: 'romance' }, { id: 9, name: 'Poesia', slug: 'poesia' }]) } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(CatalogHomeComponent);
    current = fixture;
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('mostra o texto do hero e leva "Explorar livros" ao acervo completo', async () => {
    const root = await render(of([]), of([]));
    expect(root.textContent).toContain('Consulte o acervo, solicite empréstimos ou compras e acompanhe tudo pelo LibStock.');
    const explore = Array.from(root.querySelectorAll('a')).find((a) => a.textContent?.trim() === 'Explorar livros')!;
    expect(explore.getAttribute('href')).toBe('/acervo');
    expect(root.querySelector('#categorias')).not.toBeNull();
  });

  it('lista as categorias em destaque como links para /generos/:slug e a disponibilidade dos livros', async () => {
    const root = await render(
      of([{ id: 1, name: 'Romance', slug: 'romance' }]),
      of([{
        id: 7, title: 'Sapiens', author: 'Yuval', genres: [], cover_url: null,
        offers: [{ destination: 'COMMERCIAL', available: true, price: '30.00', can_reserve: false }],
      }, {
        id: 8, title: '1984', author: 'Orwell', genres: [], cover_url: null,
        offers: [{ destination: 'DIDACTIC', available: false, price: null, can_reserve: false }],
      }]),
    );
    expect(root.querySelector('a.chip[href="/generos/romance"]')!.textContent).toContain('Romance');
    expect(root.textContent).toContain('Venda disponível');
    expect(root.textContent).toContain('Esgotado');
    expect(root.querySelector('a[href="/livros/7"]')).not.toBeNull();
  });

  it('"Ver todos" leva ao acervo completo e "Mais" abre todas as categorias', async () => {
    const root = await render(of([{ id: 1, name: 'Romance', slug: 'romance' }]), of([]));
    expect(Array.from(root.querySelectorAll('a')).find((a) => a.textContent?.includes('Ver todos'))!.getAttribute('href')).toBe('/acervo');
    const more = root.querySelector<HTMLButtonElement>('button.chip--more')!;
    expect(more.textContent!.trim()).toBe('Mais');
    more.click();
    current.detectChanges();
    const chips = Array.from(root.querySelectorAll('.chip')).map((c) => c.textContent!.trim());
    expect(chips).toEqual(['Romance', 'Poesia', 'Menos']);
  });

  it('mostra carregando, vazio e erro nas categorias e nos livros em destaque', async () => {
    const loading = await render(new Subject(), new Subject());
    expect(loading.textContent).toContain('Carregando categorias');
    expect(loading.textContent).toContain('Carregando livros');
    TestBed.resetTestingModule();
    const empty = await render(of([]), of([]));
    expect(empty.textContent).toContain('Nenhuma categoria em destaque no momento.');
    expect(empty.textContent).toContain('Nenhum livro em destaque ainda.');
    TestBed.resetTestingModule();
    const failed = await render(throwError(() => new Error('x')), throwError(() => new Error('x')));
    expect(failed.textContent).toContain('Não foi possível carregar as categorias.');
    expect(failed.textContent).toContain('Não foi possível carregar os livros em destaque.');
  });
});
