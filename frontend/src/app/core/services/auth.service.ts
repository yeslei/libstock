import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, finalize, map, of, shareReplay, tap, throwError } from 'rxjs';

import {
  AuthSession,
  LoginRequest,
  MessageResponse,
  RegisterRequest,
} from '../models/auth.model';
import { User } from '../models/user.model';
import { TokenStoreService } from './token-store.service';

export const AUTH_API = '/api/v1/auth';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly store = inject(TokenStoreService);

  /**
   * Um único refresh em voo por vez: várias requisições que tomam 401 ao mesmo
   * tempo compartilham a mesma chamada em vez de girarem o token em paralelo
   * (o backend rotaciona o refresh token e revoga a família em caso de reuso).
   */
  private refreshInFlight: Observable<AuthSession> | null = null;

  readonly user$ = this.store.user$;
  readonly isAuthenticated$ = this.store.isAuthenticated$;

  get currentUser(): User | null {
    return this.store.user;
  }

  login(payload: LoginRequest): Observable<AuthSession> {
    return this.http
      .post<AuthSession>(`${AUTH_API}/login`, payload, { withCredentials: true })
      .pipe(tap((session) => this.store.setSession(session.access_token, session.user)));
  }

  /**
   * O registro **não** devolve token — apenas o usuário criado, já com a role
   * `USER` atribuída pelo backend. O login é uma chamada separada.
   */
  register(payload: RegisterRequest): Observable<User> {
    return this.http.post<User>(`${AUTH_API}/register`, payload, { withCredentials: true });
  }

  refresh(): Observable<AuthSession> {
    this.refreshInFlight ??= this.http
      .post<AuthSession>(`${AUTH_API}/refresh`, null, { withCredentials: true })
      .pipe(
        tap((session) => this.store.setSession(session.access_token, session.user)),
        catchError((error: unknown) => {
          // 401 aqui significa cookie ausente, expirado ou reutilizado — o
          // backend já revogou a família de sessões. Só resta limpar o estado.
          this.store.clear();
          return throwError(() => error);
        }),
        finalize(() => (this.refreshInFlight = null)),
        shareReplay({ bufferSize: 1, refCount: true }),
      );

    return this.refreshInFlight;
  }

  logout(): Observable<void> {
    return this.http
      .post<MessageResponse>(`${AUTH_API}/logout`, null, { withCredentials: true })
      .pipe(
        // A sessão local cai mesmo se a chamada falhar: manter o usuário
        // "logado" após um pedido explícito de saída seria pior.
        catchError(() => of(null)),
        finalize(() => this.store.clear()),
        map(() => undefined),
      );
  }

  /** Encerra todas as sessões do usuário. Exige `Authorization: Bearer`. */
  logoutAll(): Observable<void> {
    return this.http
      .post<MessageResponse>(`${AUTH_API}/logout-all`, null, { withCredentials: true })
      .pipe(
        catchError(() => of(null)),
        finalize(() => this.store.clear()),
        map(() => undefined),
      );
  }

  /**
   * Executada no boot pelo APP_INITIALIZER. Se houver cookie de refresh válido,
   * a sessão é recuperada; caso contrário o app simplesmente inicia deslogado.
   */
  restoreSession(): Promise<void> {
    return new Promise<void>((resolve) => {
      this.refresh()
        .pipe(catchError(() => of(null)))
        .subscribe({ next: () => resolve(), error: () => resolve() });
    });
  }
}
