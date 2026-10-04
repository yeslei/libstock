import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Route, Router, provideRouter } from '@angular/router';

import { RoleCode } from './core/models/user.model';
import { AuthService } from './core/services/auth.service';
import { TokenStoreService } from './core/services/token-store.service';
import { routes } from './app.routes';

@Component({ standalone: true, template: 'tela' })
class StubComponent {}

/** Mantém caminhos, guards e dados reais das rotas, trocando apenas o carregamento dos componentes. */
function withStubs(items: Route[]): Route[] {
  return items.map(({ loadComponent: _component, loadChildren: _children, ...rest }) => {
    const copy: Route = { ...rest };
    if (rest.children) copy.children = withStubs(rest.children);
    else if (!rest.redirectTo) copy.component = StubComponent;
    return copy;
  });
}

describe('Rotas do balcão por papel (Issue #169)', () => {
  async function open(role: RoleCode, url: string): Promise<string> {
    TestBed.configureTestingModule({
      providers: [
        provideRouter(withStubs(routes)),
        { provide: AuthService, useValue: { restoreSession: () => Promise.resolve() } },
      ],
    });
    TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: [role], created_at: '' });
    const router = TestBed.inject(Router);
    await router.navigateByUrl(url);
    return router.url;
  }

  it('entrada padrão: estoquista vai ao acervo; vendedor e administrador ao painel', async () => {
    expect(await open('STOCK_KEEPER', '/balcao')).toBe('/balcao/acervo');
  });
  it('vendedor continua no painel por padrão', async () => expect(await open('SELLER', '/balcao')).toBe('/balcao/painel'));
  it('administrador continua no painel por padrão', async () => expect(await open('ADMINISTRATOR', '/balcao')).toBe('/balcao/painel'));

  for (const path of ['acervo', 'acervo/5', 'acervo/5/exemplares/novo']) {
    for (const role of ['STOCK_KEEPER', 'SELLER', 'ADMINISTRATOR'] as const) {
      it(`${role} acessa /balcao/${path}`, async () => expect(await open(role, `/balcao/${path}`)).toBe(`/balcao/${path}`));
    }
  }

  for (const path of ['painel', 'clientes', 'emprestimos', 'emprestimos/novo', 'emprestimos/solicitacoes', 'emprestimos/ativos', 'devolucoes', 'vendas', 'reservas', 'reservas/3']) {
    it(`estoquista que digita /balcao/${path} volta ao acervo`, async () => {
      expect(await open('STOCK_KEEPER', `/balcao/${path}`)).toBe('/balcao/acervo');
    });
    it(`vendedor acessa /balcao/${path}`, async () => expect(await open('SELLER', `/balcao/${path}`)).toBe(`/balcao/${path}`));
    it(`administrador acessa /balcao/${path}`, async () => expect(await open('ADMINISTRATOR', `/balcao/${path}`)).toBe(`/balcao/${path}`));
  }

  it('cliente não entra no balcão', async () => expect(await open('USER', '/balcao/acervo')).toBe('/'));

  it('endereço desconhecido dentro do balcão leva o estoquista ao acervo', async () => {
    expect(await open('STOCK_KEEPER', '/balcao/inexistente')).toBe('/balcao/acervo');
  });
  it('endereço desconhecido dentro do balcão leva o vendedor ao painel', async () => {
    expect(await open('SELLER', '/balcao/inexistente')).toBe('/balcao/painel');
  });
});
