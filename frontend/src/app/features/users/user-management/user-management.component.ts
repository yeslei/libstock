import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AdminUser, RoleCode } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { UserService } from '../../../core/services/user.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';

interface RoleOption {
  readonly label: string;
  readonly value: RoleCode;
}

const ROLE_OPTIONS: readonly RoleOption[] = [
  { label: 'Cliente', value: 'USER' },
  { label: 'Vendedor', value: 'SELLER' },
  { label: 'Estoquista', value: 'STOCK_KEEPER' },
  { label: 'Administrador', value: 'ADMINISTRATOR' },
];

const ROLE_LABELS: Readonly<Record<RoleCode, string>> = {
  USER: 'Cliente',
  SELLER: 'Vendedor',
  STOCK_KEEPER: 'Estoquista',
  ADMINISTRATOR: 'Administrador',
};

@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent, DatePipe],
  templateUrl: './user-management.component.html',
  styleUrl: './user-management.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserManagementComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly usersApi = inject(UserService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly roleOptions = ROLE_OPTIONS;
  protected readonly users = signal<AdminUser[]>([]);
  protected readonly selectedRole = signal<RoleCode | ''>('');
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly inactivatingId = signal<number | null>(null);

  ngOnInit(): void {
    this.loadUsers();
  }

  protected registerUser(): void {
    void this.router.navigate(['/gestao/funcionarios']);
  }

  protected editUser(userId: number): void {
    void this.router.navigate(['/gestao/usuarios', userId, 'editar']);
  }

  protected filterByRole(event: Event): void {
    this.selectedRole.set((event.target as HTMLSelectElement).value as RoleCode | '');
    this.loadUsers();
  }

  protected roleLabel(role: string): string {
    return ROLE_LABELS[role as RoleCode] ?? role;
  }

  protected isCurrentUser(userId: number): boolean {
    return this.auth.currentUser?.id === userId;
  }

  protected inactivate(user: AdminUser): void {
    if (!user.is_active || this.isCurrentUser(user.id) || this.inactivatingId() !== null) {
      return;
    }
    if (!window.confirm(`Inativar o acesso de ${user.name}? As sessões ativas serão encerradas.`)) {
      return;
    }

    this.error.set(null);
    this.success.set(null);
    this.inactivatingId.set(user.id);
    this.usersApi
      .inactivate(user.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.users.update((users) =>
            users.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
          );
          this.success.set(`${user.name} foi inativado com sucesso.`);
          this.inactivatingId.set(null);
        },
        error: (error: ApiError) => {
          this.error.set(error.detail || 'Não foi possível inativar o usuário.');
          this.inactivatingId.set(null);
        },
      });
  }

  private loadUsers(): void {
    this.loading.set(true);
    this.error.set(null);
    const role = this.selectedRole() || undefined;
    this.usersApi
      .list(role)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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
