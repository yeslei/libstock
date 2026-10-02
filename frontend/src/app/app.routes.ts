import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'LibStock — Gestão de acervo',
    loadComponent: () =>
      import('./features/catalog/catalog-home/catalog-home.component').then(
        (m) => m.CatalogHomeComponent,
      ),
  },
  {
    path: 'explorar',
    title: 'Explorar livros · LibStock',
    loadComponent: () =>
      import('./features/catalog/explore-books/explore-books.component').then(
        (m) => m.ExploreBooksComponent,
      ),
  },
  {
    path: 'como-funciona',
    title: 'Como funciona · LibStock',
    loadComponent: () =>
      import('./features/about/how-it-works/how-it-works.component').then(
        (m) => m.HowItWorksComponent,
      ),
  },
  {
    path: 'generos/:slug',
    title: 'Categoria · LibStock',
    loadComponent: () =>
      import('./features/catalog/genre-books/genre-books.component').then(
        (m) => m.GenreBooksComponent,
      ),
  },
  {
    path: 'obras/nova',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['STOCK_KEEPER', 'ADMINISTRATOR'] },
    title: 'Cadastrar obra · LibStock',
    loadComponent: () =>
      import('./features/books/book-create/book-create.component').then(
        (m) => m.BookCreateComponent,
      ),
  },
  {
    path: 'obras/:id/exemplares/novo',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['STOCK_KEEPER', 'ADMINISTRATOR'] },
    title: 'Cadastrar exemplar · LibStock',
    loadComponent: () =>
      import('./features/copies/copy-create/copy-create.component').then(
        (m) => m.CopyCreateComponent,
      ),
  },
  {
    path: 'gestao/acervo',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['STOCK_KEEPER', 'ADMINISTRATOR'] },
    title: 'Cadastrar exemplar · LibStock',
    loadComponent: () =>
      import('./features/stock/stock-management/stock-management.component').then(
        (m) => m.StockManagementComponent,
      ),
  },
  {
    path: 'gestao/acervo/obras/:id/editar',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['STOCK_KEEPER', 'ADMINISTRATOR'] },
    title: 'Editar obra · LibStock',
    loadComponent: () =>
      import('./features/books/book-edit/book-edit.component').then((m) => m.BookEditComponent),
  },
  {
    path: 'painel',
    pathMatch: 'full',
    canActivate: [authGuard],
    title: 'Painel · LibStock',
    loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'gestao/usuarios',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMINISTRATOR'] },
    title: 'Gestão de usuários · LibStock',
    loadComponent: () =>
      import('./features/users/user-management/user-management.component').then(
        (m) => m.UserManagementComponent,
      ),
  },
  {
    path: 'gestao/funcionarios',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMINISTRATOR'] },
    title: 'Cadastrar usuário · LibStock',
    loadComponent: () =>
      import('./features/employees/create-employee/create-employee.component').then(
        (m) => m.CreateEmployeeComponent,
      ),
  },
  {
    path: 'gestao/usuarios/:id/editar',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMINISTRATOR'] },
    title: 'Editar usuário · LibStock',
    loadComponent: () =>
      import('./features/users/user-edit/user-edit.component').then((m) => m.UserEditComponent),
  },
  {
    path: '',
    loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
