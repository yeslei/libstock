import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { RoleCode } from '../models/user.model';
import { TokenStoreService } from '../services/token-store.service';

/**
 * Restringe uma rota a determinados papéis.
 *
 * É proteção de navegação, não de segurança: o token vive no cliente e nada
 * impede alguém de forjar o estado local. Quem realmente barra é o
 * `require_roles` do backend — este guard existe para não oferecer ao usuário
 * uma tela que ele tomaria 403 ao usar.
 *
 * Uso:
 *   { path: 'admin', canActivate: [roleGuard('ADMINISTRATOR')], ... }
 */
export function roleGuard(...allowedRoles: RoleCode[]): CanActivateFn {
  const allowed = new Set<RoleCode>(allowedRoles);

  return (_route, state) => {
    const store = inject(TokenStoreService);
    const router = inject(Router);

    const user = store.user;
    if (user === null) {
      return router.createUrlTree(['/login'], {
        queryParams: { redirectTo: state.url },
      });
    }

    if (user.role_codes.some((role) => allowed.has(role))) {
      return true;
    }

    // Sem permissão manda para a home, não para o login: a sessão é válida,
    // o que falta é privilégio — devolver ao login sugeriria que reautenticar
    // resolveria.
    return router.createUrlTree(['/']);
  };
}
