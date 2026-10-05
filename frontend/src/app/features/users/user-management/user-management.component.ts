import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AdminUser, RoleCode } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { ROLE_OPTIONS, roleLabel } from '../user-labels';

@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent],
  templateUrl: './user-management.component.html',
  styleUrl: './user-management.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserManagementComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly usersApi = inject(UserService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly roleOptions = ROLE_OPTIONS;
  protected readonly roleLabel = roleLabel;
  protected readonly users = signal<AdminUser[]>([]);
  protected readonly selectedRole = signal<RoleCode | ''>('');
  protected readonly term = signal('');
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly visibleUsers = computed(() => {
    const term = this.term().trim().toLowerCase();
    return term
      ? this.users().filter((user) => `${user.name} ${user.email}`.toLowerCase().includes(term))
      : this.users();
  });

  ngOnInit(): void {
    this.loadUsers();
  }

  protected registerUser(): void {
    void this.router.navigate(['/gestao/funcionarios']);
  }

  protected editUser(userId: number): void {
    void this.router.navigate(['/gestao/usuarios', userId, 'editar']);
  }

  protected viewUser(userId: number): void {
    void this.router.navigate(['/gestao/usuarios', userId]);
  }

  protected viewPendencies(userId: number): void {
    void this.router.navigate(['/gestao/clientes', userId, 'pendencias']);
  }

  protected filterByRole(event: Event): void {
    this.selectedRole.set((event.target as HTMLSelectElement).value as RoleCode | '');
    this.loadUsers();
  }

  protected search(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
  }

  protected loadUsers(): void {
    this.loading.set(true);
    this.error.set(null);
    const role = this.selectedRole() || undefined;
    this.usersApi.list(role).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: (error: ApiError) => {
        this.users.set([]);
        this.error.set(error.detail || 'Não foi possível carregar os usuários.');
        this.loading.set(false);
      },
    });
  }
}
