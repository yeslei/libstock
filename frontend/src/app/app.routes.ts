import { Route, Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';
import { counterHomeGuard } from './features/counter/counter-home.guard';

/**
 * Issue #169: o estoquista usa o balcão restrito ao acervo. As demais telas do balcão exigem papel de atendimento;
 * quem não o tem volta ao acervo.
 */
const SERVICE_DESK_ONLY: Pick<Route, 'canActivate' | 'data'> = {
  canActivate: [roleGuard],
  data: { roles: ['SELLER', 'ADMINISTRATOR'], deniedRedirect: '/balcao/acervo' },
};

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
    path: 'comprovantes/emprestimo/:id', canActivate: [authGuard, roleGuard], data: { roles: ['USER', 'SELLER', 'ADMINISTRATOR'], receipt: 'loan' },
    title: 'Comprovante de empréstimo · LibStock',
    loadComponent: () => import('./features/receipts/receipt-page.component').then(m => m.ReceiptPageComponent),
  },
  {
    path: 'comprovantes/devolucao/:id', canActivate: [authGuard, roleGuard], data: { roles: ['USER', 'SELLER', 'ADMINISTRATOR'], receipt: 'return' },
    title: 'Comprovante de devolução · LibStock',
    loadComponent: () => import('./features/receipts/receipt-page.component').then(m => m.ReceiptPageComponent),
  },
  {
    path: 'comprovantes/venda/:id', canActivate: [authGuard, roleGuard], data: { roles: ['USER', 'SELLER', 'ADMINISTRATOR'], receipt: 'sale' },
    title: 'Comprovante de venda · LibStock',
    loadComponent: () => import('./features/receipts/receipt-page.component').then(m => m.ReceiptPageComponent),
  },
  {
    path: 'balcao', canActivate: [authGuard, roleGuard], data: { roles: ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'] },
    loadComponent: () => import('./features/counter/counter-shell.component').then(m => m.CounterShellComponent),
    children: [
      { path: '', pathMatch: 'full', canActivate: [counterHomeGuard], children: [] },
      {
        path: 'acervo', pathMatch: 'full', title: 'Acervo · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-catalog.component').then(m => m.CounterCatalogComponent),
      },
      {
        path: 'acervo/nova', title: 'Nova obra · Balcão · LibStock',
        loadComponent: () => import('./features/books/book-create/book-create.component').then(m => m.BookCreateComponent),
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
        ...SERVICE_DESK_ONLY,
        path: 'painel', title: 'Painel · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-dashboard.component').then(m => m.CounterDashboardComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'clientes', title: 'Clientes · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-pages').then(m => m.CounterClientsPageComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'emprestimos', pathMatch: 'full', title: 'Empréstimos · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-loans-home.component').then(m => m.CounterLoansHomeComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'emprestimos/novo', title: 'Novo empréstimo · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-loan-create.component').then(m => m.CounterLoanCreateComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'emprestimos/solicitacoes', title: 'Solicitações de empréstimo · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-pages').then(m => m.CounterPickupsPageComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'emprestimos/ativos', title: 'Empréstimos ativos · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-active-loans.component').then(m => m.CounterActiveLoansComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'devolucoes', title: 'Registrar devolução · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-returns.component').then(m => m.CounterReturnsComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'vendas', title: 'Registrar venda · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-sales.component').then(m => m.CounterSalesComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'reservas', pathMatch: 'full', title: 'Reservas de compra · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-reservations.component').then(m => m.CounterReservationsComponent),
      },
      {
        ...SERVICE_DESK_ONLY,
        path: 'reservas/:id', title: 'Atender reserva · Balcão · LibStock',
        loadComponent: () => import('./features/counter/counter-reservation-attend.component').then(m => m.CounterReservationAttendComponent),
      },
      { path: '**', canActivate: [counterHomeGuard], children: [] },
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
    path: 'acervo',
    title: 'Acervo completo · LibStock',
    loadComponent: () =>
      import('./features/catalog/all-books/all-books.component').then((m) => m.AllBooksComponent),
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
  // Issue #169: o cadastro de obra e exemplar passou para o balcão; os endereços antigos redirecionam para não quebrar links salvos.
  { path: 'obras/nova', pathMatch: 'full', redirectTo: '/balcao/acervo/nova' },
  { path: 'obras/:id/exemplares/novo', pathMatch: 'full', redirectTo: '/balcao/acervo/:id/exemplares/novo' },
  { path: 'gestao/acervo', pathMatch: 'full', redirectTo: '/balcao/acervo' },
  { path: 'gestao/acervo/obras/:id/editar', pathMatch: 'full', redirectTo: '/balcao/acervo/:id' },
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
