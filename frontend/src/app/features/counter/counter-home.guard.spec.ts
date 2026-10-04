import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';

import { RoleCode } from '../../core/models/user.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { counterHomeGuard } from './counter-home.guard';

describe('counterHomeGuard (entrada padrão do balcão)', () => {
  function destination(roles: RoleCode[]): string {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: roles, created_at: '' });
    const result = TestBed.runInInjectionContext(() =>
      counterHomeGuard({} as ActivatedRouteSnapshot, { url: '/balcao' } as RouterStateSnapshot));
    return TestBed.inject(Router).serializeUrl(result as UrlTree);
  }

  it('leva o estoquista ao acervo', () => expect(destination(['STOCK_KEEPER'])).toBe('/balcao/acervo'));
  it('mantém o vendedor no painel', () => expect(destination(['SELLER'])).toBe('/balcao/painel'));
  it('mantém o administrador no painel', () => expect(destination(['ADMINISTRATOR'])).toBe('/balcao/painel'));
  it('prioriza o painel para quem acumula atendimento e estoque', () => expect(destination(['STOCK_KEEPER', 'SELLER'])).toBe('/balcao/painel'));
});
