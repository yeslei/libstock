import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, RouterOutlet, provideRouter } from '@angular/router';

import { CounterShellComponent } from './counter-shell.component';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';
import { By } from '@angular/platform-browser';

@Component({ standalone: true, template: 'tela' })
class StubComponent {}

@Component({ selector: 'app-root-stub', standalone: true, imports: [RouterOutlet], template: '<router-outlet />' })
class RootComponent {}

describe('Layout do balcão (menu lateral)', () => {
  async function setup(url = '/balcao/painel') {
    TestBed.configureTestingModule({
      imports: [RootComponent],
      providers: [
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
