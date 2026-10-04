import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';
import { TokenStoreService } from '../services/token-store.service';

/** Impede que quem já está autenticado caia em /login ou /register. */
export const guestGuard: CanActivateFn = async () => {
  const store = inject(TokenStoreService);
  const router = inject(Router);
  const auth = inject(AuthService);
  await auth.restoreSession();

  return store.isAuthenticated ? router.createUrlTree(['/']) : true;
};
