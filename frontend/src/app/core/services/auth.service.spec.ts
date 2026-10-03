import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AUTH_API, AuthService } from './auth.service';
import { TokenStoreService } from './token-store.service';

describe('Session restoration', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('shares boot restoration with guards and stores the recovered session', async () => {
    const boot = auth.restoreSession();
    expect(auth.restoreSession()).toBe(boot);
    const request = http.expectOne(`${AUTH_API}/refresh`);
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ access_token: 'recovered', user: { id: 1, name: 'Maria', role_codes: ['USER'] } });
    await boot;
    expect(TestBed.inject(TokenStoreService).isAuthenticated).toBeTrue();
    await auth.restoreSession();
    http.expectNone(`${AUTH_API}/refresh`);
  });

  it('resolves as a visitor when the refresh cookie is absent', async () => {
    const restored = auth.restoreSession();
    http.expectOne(`${AUTH_API}/refresh`).flush({}, { status: 401, statusText: 'Unauthorized' });
    await restored;
    expect(TestBed.inject(TokenStoreService).isAuthenticated).toBeFalse();
  });

  it('does not restore the session from a refresh arriving after logout', async () => {
    const restored = auth.restoreSession();
    const refresh = http.expectOne(`${AUTH_API}/refresh`);
    auth.logout().subscribe();
    http.expectOne(`${AUTH_API}/logout`).flush({ message: 'ok' });
    refresh.flush({ access_token: 'old', user: { id: 1, role_codes: ['USER'] } });
    await restored;
    expect(TestBed.inject(TokenStoreService).isAuthenticated).toBeFalse();
  });

  it('does not clear a new login when an older refresh fails', async () => {
    const restored = auth.restoreSession();
    const refresh = http.expectOne(`${AUTH_API}/refresh`);
    auth.login({ email: 'maria@test.dev', password: 'password' }).subscribe();
    http.expectOne(`${AUTH_API}/login`).flush({ access_token: 'new', user: { id: 2, role_codes: ['USER'] } });
    refresh.flush({}, { status: 401, statusText: 'Unauthorized' });
    await restored;
    expect(TestBed.inject(TokenStoreService).accessToken).toBe('new');
  });
});
