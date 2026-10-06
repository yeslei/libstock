import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';

/**
 * Destino provisório após o login — existe para fechar o fluxo de
 * autenticação de ponta a ponta. Será substituído pelo dashboard real.
 */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [AsyncPipe, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly user$ = this.auth.user$;
  protected readonly leaving = signal(false);

  protected logout(): void {
    if (this.leaving()) {
      return;
    }

    this.leaving.set(true);
    this.auth
      .logout()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        complete: () => void this.router.navigate(['/login']),
      });
  }
}
