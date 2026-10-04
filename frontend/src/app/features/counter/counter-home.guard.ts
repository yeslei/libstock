import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { TokenStoreService } from '../../core/services/token-store.service';

/** Entrada do balcão: o estoquista (sem papel de atendimento) vai direto ao acervo; vendedor e administrador ao painel. */
export const counterHomeGuard: CanActivateFn = () => {
  const roles = inject(TokenStoreService).user?.role_codes ?? [];
  const serviceRole = roles.includes('SELLER') || roles.includes('ADMINISTRATOR');
  return inject(Router).createUrlTree([serviceRole ? '/balcao/painel' : '/balcao/acervo']);
};
