import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { RoleCode } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';
import { SnackbarComponent } from '../../shared/components/snackbar/snackbar.component';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';

interface NavEntry {
  /** Se informado, o item só aparece para quem tem algum destes papéis (a rota mantém seus próprios guards). */
  readonly roles?: readonly RoleCode[];
  readonly label: string;
  readonly route: string;
  readonly exact: boolean;
}

/** Papéis de atendimento; o estoquista (Issue #169) vê somente o Acervo. */
const SERVICE_ROLES: readonly RoleCode[] = ['SELLER', 'ADMINISTRATOR'];

/** Itens do menu lateral, na ordem do Figma (Funcionário / Painel). */
const NAVIGATION: readonly NavEntry[] = [
  { label: 'Painel', route: '/balcao/painel', exact: false, roles: SERVICE_ROLES },
  { label: 'Acervo', route: '/balcao/acervo', exact: false },
  { label: 'Clientes', route: '/balcao/clientes', exact: false, roles: SERVICE_ROLES },
  { label: 'Empréstimos', route: '/balcao/emprestimos', exact: false, roles: SERVICE_ROLES },
  { label: 'Devoluções', route: '/balcao/devolucoes', exact: false, roles: SERVICE_ROLES },
  { label: 'Vendas', route: '/balcao/vendas', exact: false, roles: SERVICE_ROLES },
  { label: 'Reservas', route: '/balcao/reservas', exact: false, roles: SERVICE_ROLES },
  { label: 'Usuários', route: '/gestao/usuarios', exact: false, roles: ['ADMINISTRATOR'] },
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
    (entry) => !entry.roles || (this.auth.currentUser?.role_codes ?? []).some((role) => entry.roles?.includes(role)),
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
