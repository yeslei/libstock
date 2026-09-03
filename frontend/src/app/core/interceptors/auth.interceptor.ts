import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AUTH_API, AuthService } from '../services/auth.service';
import { TokenStoreService } from '../services/token-store.service';

/** Rotas que se autenticam pelo cookie HttpOnly — não levam header Bearer. */
const COOKIE_ONLY_ENDPOINTS = [
  `${AUTH_API}/login`,
  `${AUTH_API}/register`,
  `${AUTH_API}/refresh`,
  `${AUTH_API}/logout`,
];

function isCookieOnly(request: HttpRequest<unknown>): boolean {
  return COOKIE_ONLY_ENDPOINTS.some((endpoint) => request.url.startsWith(endpoint));
}

function isApiRequest(request: HttpRequest<unknown>): boolean {
  return request.url.startsWith('/api/');
}

/**
 * Anexa credenciais a toda chamada da API:
 *
 * - `withCredentials: true` — sem isso o cookie HttpOnly de refresh não é
 *   enviado e a sessão nunca sobrevive a um reload;
 * - `Authorization: Bearer <access_token>` nas rotas que exigem o token;
 * - em 401, tenta **um** refresh e repete a requisição original. Se o refresh
 *   também falhar, limpa o estado e leva ao login (o backend revoga a família
 *   inteira de sessões quando detecta reuso de refresh token).
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const store = inject(TokenStoreService);
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!isApiRequest(request)) {
    return next(request);
  }

  const accessToken = store.accessToken;
  const authorized =
    accessToken && !isCookieOnly(request)
      ? request.clone({
          withCredentials: true,
          setHeaders: { Authorization: `Bearer ${accessToken}` },
        })
      : request.clone({ withCredentials: true });

  return next(authorized).pipe(
    catchError((error: unknown) => {
      const isUnauthorized = error instanceof HttpErrorResponse && error.status === 401;

      // Um 401 vindo do próprio fluxo de credenciais não se resolve com
      // refresh — propagar evita laço infinito.
      if (!isUnauthorized || isCookieOnly(request)) {
        return throwError(() => error);
      }

      return auth.refresh().pipe(
        switchMap((session) =>
          next(
            request.clone({
              withCredentials: true,
              setHeaders: { Authorization: `Bearer ${session.access_token}` },
            }),
          ),
        ),
        catchError((refreshError: unknown) => {
          void router.navigate(['/login'], { queryParams: { sessionExpired: true } });
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
