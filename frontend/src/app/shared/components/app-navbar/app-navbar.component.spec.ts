import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';

import { User } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { AppNavbarComponent } from './app-navbar.component';

@Component({ standalone: true, template: '' })
class NavigationStub {}

describe('AppNavbarComponent', () => {
  let fixture: ComponentFixture<AppNavbarComponent>;
  const user$ = new BehaviorSubject<User | null>(null);

  beforeEach(async () => {
    user$.next(null);
    await TestBed.configureTestingModule({
      imports: [AppNavbarComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: { user$, logout: () => of(void 0) } }],
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
  it('encaminha a busca global com o critério escolhido', () => {
    fixture.detectChanges();
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    const root = fixture.nativeElement as HTMLElement;
    const select = root.querySelector<HTMLSelectElement>('#global-criterion')!;
    select.value = 'author'; select.dispatchEvent(new Event('change'));
    const input = root.querySelector<HTMLInputElement>('#global-search')!;
    input.value = ' Machado '; input.dispatchEvent(new Event('input'));
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    expect(navigate).toHaveBeenCalledWith(['/'], { queryParams: { q: 'Machado', criterion: 'author' } });
  });

  it('encerra a sessão usando o serviço e volta ao início', () => {
    user$.next({ id: 1, name: 'Maria', email: 'm@x.dev', role_codes: ['USER'], created_at: '' });
    fixture.detectChanges();
    const auth = TestBed.inject(AuthService);
    const logout = spyOn(auth, 'logout').and.returnValue(of(void 0));
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    fixture.nativeElement.querySelector('.navbar__session button').click();
    expect(logout).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(['/']);
  });

  it('mostra os itens do cliente sem inventar rotas para funcionalidades pendentes', () => {
    user$.next({ id: 1, name: 'Maria Silva', email: 'm@x.dev', role_codes: ['USER'], created_at: '' });
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const nav = root.querySelector('nav')!;
    expect(nav.textContent).toContain('Meus empréstimos');
    expect(nav.textContent).toContain('Minhas reservas');
    expect(nav.textContent).not.toContain('Meu painel');
    expect(nav.textContent).not.toContain('Como funciona');
    expect(nav.querySelector('a[href="/meus-emprestimos"]')).not.toBeNull();
    expect(nav.querySelector('a[href="/minhas-reservas"]')).not.toBeNull();
    expect(root.querySelector('summary')!.textContent).toContain('Maria');
  });

  it('fecha o menu da conta com Escape e devolve o foco ao nome', () => {
    user$.next({ id: 1, name: 'Maria', email: 'm@x.dev', role_codes: ['USER'], created_at: '' });
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const menu = root.querySelector('details')!;
    menu.open = true;
    const summary = root.querySelector('summary')!;
    const focus = spyOn(summary, 'focus');
    summary.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(menu.open).toBeFalse();
    expect(focus).toHaveBeenCalled();
  });

  it('remove a aba Explorar acervo', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a[href="/explorar"]')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Explorar acervo');
  });

});
