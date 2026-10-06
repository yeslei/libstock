import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { TokenStoreService } from '../services/token-store.service';

/** Protege rotas privadas. O refresh do boot já rodou antes do primeiro guard. */
export const authGuard: CanActivateFn = (_route, state) => {
  const store = inject(TokenStoreService);
  const router = inject(Router);

  if (store.isAuthenticated) {
    return true;
  }

  return router.createUrlTree(['/login'], {
    queryParams: { redirectTo: state.url },
  });
};
