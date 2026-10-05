import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { NavigationEnd, NavigationStart, Router, RouterOutlet } from '@angular/router';
import { TokenStoreService } from './core/services/token-store.service';
import { AppNavbarComponent } from './shared/components/app-navbar/app-navbar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AppNavbarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@if (!staffPage()) { <app-navbar /> }<router-outlet />`,
})
export class AppComponent {
  private readonly router = inject(Router);
  private readonly account = toSignal(inject(TokenStoreService).user$);
  private readonly currentUrl = toSignal(this.router.events.pipe(filter(event => event instanceof NavigationEnd || event instanceof NavigationStart), map(event => event instanceof NavigationEnd ? event.urlAfterRedirects : (event as NavigationStart).url)), { initialValue: this.router.url });
  protected staffPage(): boolean { return ['/login', '/register'].includes(this.currentUrl().split('?')[0]) || this.currentUrl().startsWith('/balcao') || this.currentUrl().startsWith('/gestao') || !!this.account()?.role_codes.some(role => ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'].includes(role)); }
}
