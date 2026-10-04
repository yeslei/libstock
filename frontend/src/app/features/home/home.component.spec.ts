import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';

import { RoleCode, User } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';
import { HomeComponent } from './home.component';

describe('HomeComponent: link do balcão por papel', () => {
  const user$ = new BehaviorSubject<User | null>(null);

  function render(role: RoleCode): HTMLElement {
    user$.next({ id: 1, name: 'Conta', email: 'c@x.dev', role_codes: [role], created_at: '' });
    TestBed.configureTestingModule({
      imports: [HomeComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: { user$, logout: () => of(void 0) } }],
    });
    const fixture = TestBed.createComponent(HomeComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  for (const [role, visible] of [['SELLER', true], ['STOCK_KEEPER', true], ['ADMINISTRATOR', true], ['USER', false]] as const) {
    it(`${visible ? 'mostra' : 'oculta'} "Abrir balcão" para ${role}`, () => {
      expect(render(role).querySelector('a[href="/balcao"]') !== null).toBe(visible);
    });
  }
});
