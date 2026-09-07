import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { CatalogAdminService } from '../services/catalog-admin.service';
import { CatalogService } from '../services/catalog.service';
import { CatalogHomeComponent } from './catalog-home.component';

describe('CatalogHomeComponent', () => {
  let fixture: ComponentFixture<CatalogHomeComponent>;

  beforeEach(async () => {
    const user$ = new BehaviorSubject({
      id: 1, name: 'Vendedora', email: 'vendedora@teste.dev', role_codes: ['SELLER' as const], created_at: '2026-09-06',
    });
    await TestBed.configureTestingModule({
      imports: [CatalogHomeComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { user$ } },
        { provide: CatalogAdminService, useValue: { setBookFeatured: () => of(void 0) } },
        {
          provide: CatalogService,
          useValue: {
            getFeaturedGenres: () => of([]),
            getFeaturedBooks: () => of([{
              id: 42, title: 'Obra de teste', author: 'Autor', genres: [], cover_url: null, offers: [],
            }]),
            searchBooks: () => of([]),
          },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CatalogHomeComponent);
    fixture.detectChanges();
  });

  it('exibe no card o link de cadastro de exemplar usando book.id', () => {
    const link = (fixture.nativeElement as HTMLElement).querySelector<HTMLAnchorElement>(
      'a[href="/obras/42/exemplares/novo"]',
    );
    expect(link?.textContent).toContain('Cadastrar exemplar');
  });
});
