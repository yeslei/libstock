import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AdminUser } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { UserPendenciesComponent } from '../user-pendencies/user-pendencies.component';
import { isClient, rolesLabel } from '../user-labels';
import { UserPasswordResetComponent } from '../user-password-reset/user-password-reset.component';

@Component({
  selector: 'app-user-details',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent, DatePipe, RouterLink, UserPendenciesComponent, UserPasswordResetComponent],
  templateUrl: './user-details.component.html',
  styleUrl: './user-details.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserDetailsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly usersApi = inject(UserService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly userId = Number(this.route.snapshot.paramMap.get('id'));

  protected readonly loading = signal(true);
  protected readonly user = signal<AdminUser | null>(null);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    if (!Number.isInteger(this.userId) || this.userId <= 0) {
      this.error.set('Identificador de usuário inválido.');
      this.loading.set(false);
      return;
    }
    this.usersApi.get(this.userId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (user) => { this.user.set(user); this.loading.set(false); },
      error: (error: ApiError) => {
        this.error.set(error.detail || 'Não foi possível carregar o usuário.');
        this.loading.set(false);
      },
    });
  }

  protected roles(user: AdminUser): string { return rolesLabel(user.role_codes); }
  protected client(user: AdminUser): boolean { return isClient(user.role_codes); }
  protected back(): void { void this.router.navigate(['/gestao/usuarios']); }
}
