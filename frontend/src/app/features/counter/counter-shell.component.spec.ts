import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, RouterOutlet, provideRouter } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { CounterShellComponent } from './counter-shell.component';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';
import { By } from '@angular/platform-browser';

@Component({ standalone: true, template: 'tela' })
class StubComponent {}

@Component({ selector: 'app-root-stub', standalone: true, imports: [RouterOutlet], template: '<router-outlet />' })
class RootComponent {}

describe('Layout do balcão (menu lateral)', () => {
  async function setup(url = '/balcao/painel', roles: string[] = ['SELLER']) {
    TestBed.configureTestingModule({
      imports: [RootComponent],
      providers: [
        { provide: AuthService, useValue: { currentUser: { id: 1, role_codes: roles } } },
        provideRouter([
          {
            path: 'balcao',
            component: CounterShellComponent,
            children: [
              { path: 'painel', component: StubComponent },
              { path: 'clientes', component: StubComponent },
              { path: 'emprestimos/solicitacoes', component: StubComponent },
              { path: 'devolucoes', component: StubComponent },
              { path: 'reservas/:id', component: StubComponent },
            ],
          },
          { path: '', component: StubComponent },
        ]),
      ],
    });
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(RootComponent);
    await router.navigateByUrl(url);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, router, root: fixture.nativeElement as HTMLElement };
  }

  it('lista os itens na ordem do Figma', async () => {
    const { root } = await setup();
    const labels = Array.from(root.querySelectorAll('nav a')).map((a) => a.textContent?.trim());
    expect(labels).toEqual(['Painel', 'Acervo', 'Clientes', 'Empréstimos', 'Devoluções', 'Vendas', 'Reservas']);
    expect(root.querySelector('.shell__brand')?.textContent).toBe('LibStock');
  });

  it('marca o item atual com aria-current e o destaque lateral', async () => {
    const { root } = await setup('/balcao/emprestimos/solicitacoes');
    const current = Array.from(root.querySelectorAll('nav a')).filter((a) => a.getAttribute('aria-current') === 'page');
    expect(current.map((a) => a.textContent?.trim())).toEqual(['Empréstimos']);
    expect(current[0].classList).toContain('shell__link--active');
  });

  it('mantém Reservas ativo também na tela de atendimento', async () => {
    const { root } = await setup('/balcao/reservas/31');
    const current = Array.from(root.querySelectorAll('nav a')).filter((a) => a.getAttribute('aria-current') === 'page');
    expect(current.map((a) => a.textContent?.trim())).toEqual(['Reservas']);
  });

  it('expõe um botão de menu recolhível com estado acessível', async () => {
    const { fixture, root } = await setup();
    const toggle = root.querySelector('.shell__toggle') as HTMLButtonElement;
    expect(toggle.getAttribute('aria-controls')).toBe('counter-menu');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    toggle.click();
    fixture.detectChanges();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(root.querySelector('#counter-menu')?.classList).toContain('shell__side--open');
  });

  it('fecha o menu ao navegar', async () => {
    const { fixture, router, root } = await setup();
    (root.querySelector('.shell__toggle') as HTMLButtonElement).click();
    fixture.detectChanges();
    await router.navigateByUrl('/balcao/clientes');
    fixture.detectChanges();
    expect(root.querySelector('.shell__toggle')?.getAttribute('aria-expanded')).toBe('false');
  });

  it('hospeda feedback uma única vez e o descarta ao sair do balcão', async () => {
    const { fixture, router, root } = await setup();
    const service = fixture.debugElement.query(By.directive(CounterShellComponent)).injector.get(SnackbarService);
    service.show('Operação confirmada.', 'success');
    fixture.detectChanges();
    expect(root.querySelectorAll('app-snackbar').length).toBe(1);
    expect(root.querySelector('.snackbar')?.textContent).toContain('Operação confirmada.');
    await router.navigateByUrl('/');
    fixture.detectChanges();
    expect(service.notification()).toBeNull();
    await router.navigateByUrl('/balcao/painel');
    fixture.detectChanges();
    expect(root.querySelector('.snackbar')).toBeNull();
  });
});

describe('Layout do balcão (item Usuários por papel)', () => {
  async function render(roles: string[]) {
    TestBed.configureTestingModule({
      imports: [RootComponent],
      providers: [
        { provide: AuthService, useValue: { currentUser: { id: 1, role_codes: roles } } },
        provideRouter([
          { path: 'balcao', component: CounterShellComponent, children: [{ path: 'painel', component: StubComponent }] },
          { path: 'gestao/usuarios', component: StubComponent },
        ]),
      ],
    });
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(RootComponent);
    await router.navigateByUrl('/balcao/painel');
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('mostra Usuários apenas para administrador, apontando para a gestão existente', async () => {
    const root = await render(['ADMINISTRATOR']);
    const link = Array.from(root.querySelectorAll('nav a')).find((a) => a.textContent?.trim() === 'Usuários');
    expect(link?.getAttribute('href')).toBe('/gestao/usuarios');
  });

  it('oculta Usuários do vendedor', async () => {
    const root = await render(['SELLER']);
    const labels = Array.from(root.querySelectorAll('nav a')).map((a) => a.textContent?.trim());
    expect(labels).not.toContain('Usuários');
  });
});

describe('Layout do balcão (menu do estoquista, Issue #169)', () => {
  async function labelsFor(roles: string[]) {
    TestBed.configureTestingModule({
      imports: [RootComponent],
      providers: [
        { provide: AuthService, useValue: { currentUser: { id: 1, role_codes: roles } } },
        provideRouter([
          { path: 'balcao', component: CounterShellComponent, children: [{ path: 'acervo', component: StubComponent }] },
        ]),
      ],
    });
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(RootComponent);
    await router.navigateByUrl('/balcao/acervo');
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('nav a')).map((a) => a.textContent?.trim());
  }

  it('mostra somente Acervo para STOCK_KEEPER', async () => {
    expect(await labelsFor(['STOCK_KEEPER'])).toEqual(['Acervo']);
  });

  it('mantém o menu completo para ADMINISTRATOR', async () => {
    expect(await labelsFor(['ADMINISTRATOR'])).toEqual(['Painel', 'Acervo', 'Clientes', 'Empréstimos', 'Devoluções', 'Vendas', 'Reservas', 'Usuários']);
  });

  it('mantém o menu de atendimento para quem acumula estoquista e vendedor', async () => {
    expect(await labelsFor(['STOCK_KEEPER', 'SELLER'])).toEqual(['Painel', 'Acervo', 'Clientes', 'Empréstimos', 'Devoluções', 'Vendas', 'Reservas']);
  });
});
