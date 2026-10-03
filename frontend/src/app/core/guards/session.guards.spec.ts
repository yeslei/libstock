import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, provideRouter } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { TokenStoreService } from '../services/token-store.service';
import { authGuard } from './auth.guard';
import { guestGuard } from './guest.guard';
import { roleGuard } from './role.guard';

describe('Guards during session restoration', () => {
  let resolve: () => void;
  let store: TokenStoreService;
  const route = {} as ActivatedRouteSnapshot;
  const state = { url: '/gestao/usuarios' } as RouterStateSnapshot;
  beforeEach(() => {
    const restoration = new Promise<void>((done) => { resolve = done; });
    TestBed.configureTestingModule({ providers: [
      provideRouter([]),
      { provide: AuthService, useValue: { restoreSession: () => restoration } },
    ] });
    store = TestBed.inject(TokenStoreService);
  });
  function recover(): void {
    store.setSession('token', { id: 1, name: 'Maria', email: 'm@x.dev', role_codes: ['USER'], created_at: '' });
    resolve();
  }
  it('waits for restoration before allowing private navigation', async () => {
    const pending = TestBed.runInInjectionContext(() => authGuard(route, state));
    recover();
    expect(await pending).toBeTrue();
  });
  it('preserves the requested private URL for a visitor', async () => {
    const pending = TestBed.runInInjectionContext(() => authGuard(route, state));
    resolve();
    expect(String(await pending)).toBe('/login?redirectTo=%2Fgestao%2Fusuarios');
  });
  it('avoids displaying the login form to a recovered user', async () => {
    const pending = TestBed.runInInjectionContext(() => guestGuard(route, state));
    recover();
    expect(String(await pending)).toBe('/');
  });
  it('waits for restoration when role and authentication guards run together', async () => {
    const auth = TestBed.runInInjectionContext(() => authGuard(route, state));
    const role = TestBed.runInInjectionContext(() => roleGuard({ data: { roles: ['USER'] } } as unknown as ActivatedRouteSnapshot, state));
    recover();
    expect(await auth).toBeTrue();
    expect(await role).toBeTrue();
  });
});
