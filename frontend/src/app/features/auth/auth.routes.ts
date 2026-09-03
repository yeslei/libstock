import { Routes } from '@angular/router';

import { guestGuard } from '../../core/guards/guest.guard';
import { AuthLayoutComponent } from './auth-layout/auth-layout.component';

/**
 * Carregadas sob demanda: quem já tem sessão restaurada no boot nunca baixa
 * este pedaço do bundle.
 */
export const AUTH_ROUTES: Routes = [
  {
    path: '',
    component: AuthLayoutComponent,
    canActivate: [guestGuard],
    children: [
      {
        path: 'login',
        title: 'Entrar · LibStock',
        loadComponent: () => import('./login/login.component').then((m) => m.LoginComponent),
      },
      {
        path: 'register',
        title: 'Criar conta · LibStock',
        loadComponent: () =>
          import('./register/register.component').then((m) => m.RegisterComponent),
      },
      { path: '', pathMatch: 'full', redirectTo: 'login' },
    ],
  },
];
