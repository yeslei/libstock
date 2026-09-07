import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canActivate: [authGuard],
    title: 'Início · LibStock',
    loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'gestao/funcionarios',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMINISTRATOR'] },
    title: 'Cadastrar funcionário · LibStock',
    loadComponent: () =>
      import('./features/employees/create-employee/create-employee.component').then(
        (m) => m.CreateEmployeeComponent,
      ),
  },
  {
    path: '',
    loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
