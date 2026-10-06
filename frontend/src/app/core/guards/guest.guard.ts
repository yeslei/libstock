import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { TokenStoreService } from '../services/token-store.service';

/** Impede que quem já está autenticado caia em /login ou /register. */
export const guestGuard: CanActivateFn = () => {
  const store = inject(TokenStoreService);
  const router = inject(Router);

  return store.isAuthenticated ? router.createUrlTree(['/']) : true;
};
