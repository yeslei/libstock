import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { RoleCode } from '../models/user.model';
import { TokenStoreService } from '../services/token-store.service';
import { AuthService } from '../services/auth.service';

export const roleGuard: CanActivateFn = async (route) => {
  const store = inject(TokenStoreService);
  const router = inject(Router);
  const roles = route.data['roles'];
  const auth = inject(AuthService);
  await auth.restoreSession();

  if (!store.isAuthenticated) {
    return router.createUrlTree(['/login']);
  }

  if (!Array.isArray(roles) || roles.length === 0) {
    return true;
  }

  const allowedRoles = roles as readonly RoleCode[];
  const userRoles = store.user?.role_codes ?? [];

  if (userRoles.some((role) => allowedRoles.includes(role))) {
    return true;
  }

  /** Rotas podem indicar para onde mandar o papel sem acesso (ex.: estoquista no balcão volta ao acervo). */
  const fallback = route.data['deniedRedirect'];
  return router.createUrlTree([typeof fallback === 'string' ? fallback : '/']);
};
