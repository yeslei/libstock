import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppNavbarComponent } from './shared/components/app-navbar/app-navbar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AppNavbarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<app-navbar /><router-outlet />`,
})
export class AppComponent {}
