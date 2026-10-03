import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

interface NavEntry {
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
];

/** Layout da área do funcionário: menu lateral (recolhível em telas pequenas) e conteúdo da rota filha. */
@Component({
  selector: 'app-counter-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-shell.component.html',
  styleUrl: './counter-shell.component.scss',
})
export class CounterShellComponent {
  protected readonly navigation = NAVIGATION;
  protected readonly menuOpen = signal(false);

  constructor() {
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
