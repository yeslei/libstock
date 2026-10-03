import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';
import { TokenStoreService } from '../services/token-store.service';

/** Protege rotas privadas. Aguarda a sessão sem bloquear a vitrine pública. */
export const authGuard: CanActivateFn = async (_route, state) => {
  const store = inject(TokenStoreService);
  const router = inject(Router);
  const auth = inject(AuthService);
  await auth.restoreSession();

  if (store.isAuthenticated) {
    return true;
  }

  return router.createUrlTree(['/login'], {
    queryParams: { redirectTo: state.url },
  });
};
