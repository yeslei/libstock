import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { RoleCode } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';
import { SnackbarComponent } from '../../shared/components/snackbar/snackbar.component';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';

interface NavEntry {
  /** Se informado, o item só aparece para este papel (a rota mantém seus próprios guards). */
  readonly role?: RoleCode;
  readonly label: string;
  readonly route: string;
  readonly exact: boolean;
}

/** Itens do menu lateral, na ordem do Figma (Funcionário / Painel).  */
const NAVIGATION: readonly NavEntry[] = [
  { label: 'Painel', route: '/balcao/painel', exact: false },
  { label: 'Acervo', route: '/balcao/acervo', exact: false },
  { label: 'Clientes', route: '/balcao/clientes', exact: false },
  { label: 'Empréstimos', route: '/balcao/emprestimos', exact: false },
  { label: 'Devoluções', route: '/balcao/devolucoes', exact: false },
  { label: 'Vendas', route: '/balcao/vendas', exact: false },
  { label: 'Reservas', route: '/balcao/reservas', exact: false },
  { label: 'Usuários', route: '/gestao/usuarios', exact: false, role: 'ADMINISTRATOR' },
];

/** Layout da área do funcionário: menu lateral (recolhível em telas pequenas) e conteúdo da rota filha. */
@Component({
  selector: 'app-counter-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, SnackbarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-shell.component.html',
  styleUrl: './counter-shell.component.scss',
})
export class CounterShellComponent {
  private readonly auth = inject(AuthService);
  protected readonly navigation = NAVIGATION.filter(
    (entry) => !entry.role || (this.auth.currentUser?.role_codes ?? []).includes(entry.role),
  );
  protected readonly menuOpen = signal(false);

  constructor() {
    const snackbar = inject(SnackbarService);
    inject(DestroyRef).onDestroy(() => snackbar.dismiss());
    inject(Router)
      .events.pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.menuOpen.set(false));
  }

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }
}
