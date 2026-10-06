import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { TokenStoreService } from '../services/token-store.service';

/** A vitrine abre imediatamente; funcionários são encaminhados após a restauração. */
export const homeGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const store = inject(TokenStoreService);
  const router = inject(Router);
  const isStaff = () => store.user?.role_codes.some(role => ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'].includes(role));
  const restored = auth.restoreSession();
  if (isStaff()) return router.createUrlTree(['/balcao']);
  void restored.then(() => {
    // Não interrompe quem já saiu da página inicial durante a restauração.
    if (isStaff() && router.url === (state.url || '/')) void router.navigateByUrl('/balcao');
  });
  return true;
};
