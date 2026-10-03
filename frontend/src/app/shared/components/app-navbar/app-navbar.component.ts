import { ChangeDetectionStrategy, Component, computed, inject, DestroyRef, ElementRef, HostListener, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';


import { RoleCode } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';

interface NavItem {
  readonly label: string;
  readonly route?: string;
  readonly roles?: readonly RoleCode[];
}

const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Início', route: '/' },
  { label: 'Meus empréstimos', route: '/meus-emprestimos', roles: ['USER'] },
  { label: 'Minhas reservas', route: '/minhas-reservas', roles: ['USER'] },
  { label: 'Balcão', route: '/balcao', roles: ['SELLER', 'ADMINISTRATOR'] },

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
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly accountMenu = viewChild<ElementRef<HTMLDetailsElement>>('accountMenu');

  @HostListener('document:click', ['$event'])
  protected closeAccountOnOutsideClick(event: MouseEvent): void {
    const menu = this.accountMenu()?.nativeElement;
    if (menu && event.target instanceof Node && !menu.contains(event.target)) menu.open = false;
  }

  protected readonly query = signal('');
  protected readonly criterion = signal('title');
  protected readonly signingOut = signal(false);

  protected search(event: Event): void {
    event.preventDefault();
    const q = this.query().trim();
    if (q) void this.router.navigate(['/'], { queryParams: { q, criterion: this.criterion() } });
  }

  protected logout(): void {
    if (this.signingOut()) return;
    this.signingOut.set(true);
    this.auth.logout().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      this.signingOut.set(false);
      void this.router.navigate(['/']);
    });
  }

  protected readonly user = toSignal(this.auth.user$, { initialValue: null });
  protected readonly items = computed<readonly NavItem[]>(() => {
    const roles = new Set(this.user()?.role_codes ?? []);
    const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.some((role) => roles.has(role)));
    return items;
  });
}
