import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'LibStock — Encontre livros, compartilhe histórias',
    loadComponent: () =>
      import('./features/catalog/catalog-home/catalog-home.component').then(
        (m) => m.CatalogHomeComponent,
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
    canActivate: [authGuard],
    title: 'Cadastrar obra · LibStock',
    loadComponent: () =>
      import('./features/books/book-create/book-create.component').then(
        (m) => m.BookCreateComponent,
      ),
  },
  {
    path: 'painel',
    pathMatch: 'full',
    canActivate: [authGuard],
    title: 'Painel · LibStock',
    loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: '',
    loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
