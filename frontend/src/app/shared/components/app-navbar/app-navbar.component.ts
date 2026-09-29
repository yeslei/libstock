import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { RoleCode } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';

interface NavItem {
  readonly label: string;
  readonly route: string;
  readonly roles?: readonly RoleCode[];
}

const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Início', route: '/' },
  { label: 'Explorar livros', route: '/explorar' },
  { label: 'Como funciona', route: '/como-funciona' },
  { label: 'Meu painel', route: '/painel', roles: ['USER', 'SELLER'] },
  {
    label: 'Cadastrar exemplar',
    route: '/gestao/acervo',
    roles: ['STOCK_KEEPER', 'ADMINISTRATOR'],
  },
  { label: 'Gestão de usuários', route: '/gestao/usuarios', roles: ['ADMINISTRATOR'] },
];

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app-navbar.component.html',
  styleUrl: './app-navbar.component.scss',
})
export class AppNavbarComponent {
  private readonly auth = inject(AuthService);
  protected readonly user = toSignal(this.auth.user$, { initialValue: null });
  protected readonly items = computed(() => {
    const roles = new Set(this.user()?.role_codes ?? []);
    return NAV_ITEMS.filter((item) => !item.roles || item.roles.some((role) => roles.has(role)));
  });
}
