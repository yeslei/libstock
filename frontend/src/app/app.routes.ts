import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: 'meus-emprestimos', canActivate: [authGuard, roleGuard], data: { roles: ['USER'], tracking: 'loans' },
    title: 'Meus empréstimos · LibStock',
    loadComponent: () => import('./features/client-tracking/client-tracking.component').then(m => m.ClientTrackingComponent),
  },
  {
    path: 'minhas-reservas', canActivate: [authGuard, roleGuard], data: { roles: ['USER'], tracking: 'reservations' },
    title: 'Minhas reservas · LibStock',
    loadComponent: () => import('./features/client-tracking/client-tracking.component').then(m => m.ClientTrackingComponent),
  },
  {
    path: 'balcao', canActivate: [authGuard, roleGuard], data: { roles: ['SELLER', 'ADMINISTRATOR'] },
    loadComponent: () => import('./features/counter/counter-shell.component').then(m => m.CounterShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'painel' },
      {
        path: 'painel', title: 'Painel · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-dashboard.component').then(m => m.CounterDashboardComponent),
      },
      {
        path: 'acervo', pathMatch: 'full', title: 'Acervo · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-catalog.component').then(m => m.CounterCatalogComponent),
      },
      {
        path: 'acervo/:id/exemplares/novo', title: 'Novo exemplar · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-copy-create.component').then(m => m.CounterCopyCreateComponent),
      },
      {
        path: 'acervo/:id', title: 'Obra · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-catalog-book.component').then(m => m.CounterCatalogBookComponent),
      },
      {
        path: 'clientes', title: 'Clientes · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-pages').then(m => m.CounterClientsPageComponent),
      },
      {
        path: 'emprestimos', pathMatch: 'full', title: 'Empréstimos · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-loans-home.component').then(m => m.CounterLoansHomeComponent),
      },
      {
        path: 'emprestimos/novo', title: 'Novo empréstimo · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-loan-create.component').then(m => m.CounterLoanCreateComponent),
      },
      {
        path: 'emprestimos/solicitacoes', title: 'Solicitações de empréstimo · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-pages').then(m => m.CounterPickupsPageComponent),
      },
      {
        path: 'emprestimos/ativos', title: 'Empréstimos ativos · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-active-loans.component').then(m => m.CounterActiveLoansComponent),
      },
      {
        path: 'devolucoes', title: 'Registrar devolução · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-returns.component').then(m => m.CounterReturnsComponent),
      },
      {
        path: 'vendas', title: 'Registrar venda · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-sales.component').then(m => m.CounterSalesComponent),
      },
      {
        path: 'reservas', pathMatch: 'full', title: 'Reservas de compra · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-reservations.component').then(m => m.CounterReservationsComponent),
      },
      {
        path: 'reservas/:id', title: 'Atender reserva · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-reservation-attend.component').then(m => m.CounterReservationAttendComponent),
      },
      { path: '**', redirectTo: 'painel' },
    ],
  },
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
    redirectTo: '',
    pathMatch: 'full',
  },
  {
    path: 'livros/:id',
    title: 'Detalhes do livro · LibStock',
    loadComponent: () =>
      import('./features/catalog/book-details/book-details.component').then(
        (m) => m.BookDetailsComponent,
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
    data: { roles: ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'] },
    title: 'Cadastrar obra · LibStock',
    loadComponent: () =>
      import('./features/books/book-create/book-create.component').then(
        (m) => m.BookCreateComponent,
      ),
  },
  {
    path: 'obras/:id/exemplares/novo',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'] },
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
    path: 'gestao/usuarios/:id',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['ADMINISTRATOR'] },
    title: 'Detalhes do usuário · LibStock',
    loadComponent: () =>
      import('./features/users/user-details/user-details.component').then(
        (m) => m.UserDetailsComponent,
      ),
  },
  {
    path: '',
    loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
