import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { TokenStoreService } from '../services/token-store.service';
import { RoleCode } from '../models/user.model';
import { homeGuard } from './home.guard';

describe('Entrada inicial por perfil', () => {
  it('permite consultar a página inicial sem sessão válida', async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: AuthService, useValue: { restoreSession: async () => {} } }] });
    const result = await TestBed.runInInjectionContext(() => homeGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot));
    expect(result).toBeTrue();
  });
  for (const role of ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR', 'USER'] as RoleCode[]) {
    it(`restaura a sessão de ${role} antes de escolher a página inicial`, async () => {
      TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: AuthService, useValue: {
        restoreSession: async () => TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: [role], created_at: '' }),
      } }] });
      const result = await TestBed.runInInjectionContext(() => homeGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot));
      if (role === 'USER') expect(result).toBeTrue();
      else expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/balcao');
    });
  }
});


describe('Entrada pública com restauração lenta', () => {
  it('libera a vitrine imediatamente e encaminha o funcionário quando a sessão chega', async () => {
    let resolve!: () => void;
    const pending = new Promise<void>(done => resolve = done);
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: AuthService, useValue: { restoreSession: () => pending } }] });
    const router = TestBed.inject(Router);
    const navigate = spyOn(router, 'navigateByUrl').and.resolveTo(true);
    const result = TestBed.runInInjectionContext(() => homeGuard({} as ActivatedRouteSnapshot, { url: '/' } as RouterStateSnapshot));
    expect(result).toBeTrue();
    TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: ['SELLER'], created_at: '' });
    resolve(); await pending;
    expect(navigate).toHaveBeenCalledWith('/balcao');
  });
});
