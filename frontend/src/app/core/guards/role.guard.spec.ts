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
import { AuthService } from '../services/auth.service';
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
      providers: [provideRouter([{ path: '', component: class HomeStub {} }]),
        { provide: AuthService, useValue: { restoreSession: () => Promise.resolve() } }],
    });

    store = TestBed.inject(TokenStoreService);
    store.clear();
  });

  it('bloqueia a rota para usuário sem autenticação', async () => {
    const result = await TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/login');
  });

  it('bloqueia a rota para usuário autenticado sem ADMINISTRATOR', async () => {
    store.setSession('token', user(['SELLER']));

    const result = await TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  (['USER', 'SELLER', 'STOCK_KEEPER'] as const).forEach((role) => {
    it(`bloqueia a rota para o papel ${role}`, async () => {
      store.setSession('token', user([role]));

      const result = await TestBed.runInInjectionContext(() =>
        roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
      );

      expect(result instanceof UrlTree).toBeTrue();
      expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
    });
  });

  it('bloqueia a rota quando o usuário está ausente', async () => {
    const result = await TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/login');
  });

  it('bloqueia a rota quando role_codes está ausente', async () => {
    const incompleteUser = { ...user([]), role_codes: undefined } as unknown as User;
    store.setSession('token', incompleteUser);

    const result = await TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  it('bloqueia a rota quando role_codes está vazio', async () => {
    store.setSession('token', user([]));

    const result = await TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  it('permite acesso para ADMINISTRATOR', async () => {
    store.setSession('token', user(['ADMINISTRATOR']));

    const result = await TestBed.runInInjectionContext(() =>
      roleGuard(routeWithRoles(['ADMINISTRATOR']), routerState()),
    );

    expect(result).toBeTrue();
  });
});

describe('roleGuard com deniedRedirect', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: { restoreSession: () => Promise.resolve() } }],
    });
    TestBed.inject(TokenStoreService).setSession('token', user(['STOCK_KEEPER']));
  });

  function run(data: Record<string, unknown>) {
    return TestBed.runInInjectionContext(() =>
      roleGuard({ data } as unknown as ActivatedRouteSnapshot, routerState()));
  }

  it('redireciona o papel sem acesso para o destino indicado na rota', async () => {
    const result = await run({ roles: ['SELLER'], deniedRedirect: '/balcao/acervo' });
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/balcao/acervo');
  });

  it('não redireciona quem tem acesso', async () => {
    expect(await run({ roles: ['STOCK_KEEPER'], deniedRedirect: '/balcao/acervo' })).toBeTrue();
  });
});
