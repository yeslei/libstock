import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, map } from 'rxjs';

import { User } from '../models/user.model';

/**
 * Guarda o access token **apenas em memória**.
 *
 * localStorage/sessionStorage seriam legíveis por qualquer script injetado
 * (XSS). O refresh token vive em cookie HttpOnly, gerenciado pelo browser e
 * inacessível ao JS — a sessão sobrevive a reloads via `POST /refresh`, não via
 * persistência do access token no cliente.
 */
@Injectable({ providedIn: 'root' })
export class TokenStoreService {
  private readonly accessToken$$ = new BehaviorSubject<string | null>(null);
  private readonly user$$ = new BehaviorSubject<User | null>(null);

  readonly accessToken$: Observable<string | null> = this.accessToken$$.asObservable();
  readonly user$: Observable<User | null> = this.user$$.asObservable();
  readonly isAuthenticated$: Observable<boolean> = this.user$$.pipe(map((user) => user !== null));

  /** Leitura síncrona — usada pelo interceptor ao montar o header. */
  get accessToken(): string | null {
    return this.accessToken$$.value;
  }

  get user(): User | null {
    return this.user$$.value;
  }

  get isAuthenticated(): boolean {
    return this.user$$.value !== null;
  }

  setSession(accessToken: string, user: User): void {
    this.accessToken$$.next(accessToken);
    this.user$$.next(user);
  }

  clear(): void {
    this.accessToken$$.next(null);
    this.user$$.next(null);
  }
}
