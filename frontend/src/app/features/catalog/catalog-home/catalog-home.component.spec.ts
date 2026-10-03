import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of } from 'rxjs';
import { CatalogBook } from '../models/catalog.model';

import { AuthService } from '../../../core/services/auth.service';
import { CatalogAdminService } from '../services/catalog-admin.service';
import { CatalogService } from '../services/catalog.service';
import { CatalogHomeComponent } from './catalog-home.component';

describe('CatalogHomeComponent', () => {
  let fixture: ComponentFixture<CatalogHomeComponent>;
  const params = new BehaviorSubject(convertToParamMap({}));
  let search: jasmine.Spy;

  beforeEach(async () => {
    params.next(convertToParamMap({}));
    search = jasmine.createSpy('searchBooks').and.returnValue(of([]));
    const user$ = new BehaviorSubject({
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
