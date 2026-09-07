import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  provideRouter,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';

import { RoleCode, User } from '../models/user.model';
import { TokenStoreService } from '../services/token-store.service';
import { roleGuard } from './role.guard';

const user = (roleCodes: RoleCode[]): User => ({
  id: 1,
  name: 'Admin',
  email: 'admin@libstock.com',
  role_codes: roleCodes,
  created_at: '2026-09-06T00:00:00Z',
});

function routeWithRoles(roles: RoleCode[]): ActivatedRouteSnapshot {
  return { data: { roles } } as unknown as ActivatedRouteSnapshot;
}

function routerState(): RouterStateSnapshot {
  return { url: '/gestao/funcionarios' } as RouterStateSnapshot;
}

describe('roleGuard', () => {
  let store: TokenStoreService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([{ path: '', component: class HomeStub {} }])],
    });

    store = TestBed.inject(TokenStoreService);
    store.clear();
  });

  it('bloqueia a rota para usuário sem autenticação', () => {
    const result = TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/login');
  });

  it('bloqueia a rota para usuário autenticado sem ADMINISTRATOR', () => {
    store.setSession('token', user(['SELLER']));

    const result = TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  (['USER', 'ATTENDANT', 'SELLER', 'STOCK_KEEPER', 'MANAGER'] as const).forEach((role) => {
    it(`bloqueia a rota para o papel ${role}`, () => {
      store.setSession('token', user([role]));

      const result = TestBed.runInInjectionContext(() =>
        roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
      );

      expect(result instanceof UrlTree).toBeTrue();
      expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
    });
  });

  it('bloqueia a rota quando o usuário está ausente', () => {
    const result = TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/login');
  });

  it('bloqueia a rota quando role_codes está ausente', () => {
    const incompleteUser = { ...user([]), role_codes: undefined } as unknown as User;
    store.setSession('token', incompleteUser);

    const result = TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  it('bloqueia a rota quando role_codes está vazio', () => {
    store.setSession('token', user([]));

    const result = TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  it('permite acesso para ADMINISTRATOR', () => {
    store.setSession('token', user(['ADMINISTRATOR']));

    const result = TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result).toBeTrue();
  });
});
