import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { User } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { AppNavbarComponent } from './app-navbar.component';

describe('AppNavbarComponent', () => {
  let fixture: ComponentFixture<AppNavbarComponent>;
  const user$ = new BehaviorSubject<User | null>(null);

  beforeEach(async () => {
    user$.next(null);
    await TestBed.configureTestingModule({
      imports: [AppNavbarComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: { user$ } }],
    }).compileComponents();
    fixture = TestBed.createComponent(AppNavbarComponent);
  });

  function text(): string { fixture.detectChanges(); return fixture.nativeElement.textContent; }

  it('mostra um único cadastro de exemplar para estoquista', () => {
    user$.next({ id: 1, name: 'Estoque', email: 'e@x.dev', role_codes: ['STOCK_KEEPER'], created_at: '' });
    expect(text().match(/Cadastrar exemplar/g)?.length).toBe(1);
    expect(fixture.nativeElement.querySelector('a[href="/gestao/acervo"]')).not.toBeNull();
  });

  it('não mostra gestão de acervo para vendedor ou usuário', () => {
    user$.next({ id: 2, name: 'Venda', email: 'v@x.dev', role_codes: ['SELLER'], created_at: '' });
    expect(text()).not.toContain('Cadastrar exemplar');
  });

  it('une capacidades sem duplicar links', () => {
    user$.next({ id: 3, name: 'Admin', email: 'a@x.dev', role_codes: ['STOCK_KEEPER', 'ADMINISTRATOR'], created_at: '' });
    const content = text();
    expect(content.match(/Cadastrar exemplar/g)?.length).toBe(1);
    expect(content).toContain('Gestão de usuários');
  });
});
