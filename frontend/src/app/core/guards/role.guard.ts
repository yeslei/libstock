import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { RoleCode } from '../models/user.model';
import { TokenStoreService } from '../services/token-store.service';

export const roleGuard: CanActivateFn = (route) => {
  const store = inject(TokenStoreService);
  const router = inject(Router);
  const roles = route.data['roles'];

  if (!store.isAuthenticated) {
    return router.createUrlTree(['/login']);
  }

  if (!Array.isArray(roles) || roles.length === 0) {
    return true;
  }

  const allowedRoles = roles as readonly RoleCode[];
  const userRoles = store.user?.role_codes ?? [];

  return userRoles.some((role) => allowedRoles.includes(role)) ? true : router.createUrlTree(['/']);
};
