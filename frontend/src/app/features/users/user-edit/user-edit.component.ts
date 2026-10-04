import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AdminUser, RoleCode } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SnackbarComponent } from '../../../shared/components/snackbar/snackbar.component';
import { SnackbarService } from '../../../shared/components/snackbar/snackbar.service';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { emailFormat } from '../../../shared/validators/email.validator';
import { fieldError } from '../../../shared/validators/form-errors';
import { UserPendenciesComponent } from '../user-pendencies/user-pendencies.component';
import { ROLE_OPTIONS, isClient, roleLabel } from '../user-labels';

type Confirmation = 'inactivate' | 'role';

function nonBlank(control: AbstractControl<string>): ValidationErrors | null {
  return control.value.trim().length === 0 ? { blank: true } : null;
}

@Component({
  selector: 'app-user-edit',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AlertComponent,
    SnackbarComponent,
    SpinnerComponent,
    UserPendenciesComponent,
  ],
  templateUrl: './user-edit.component.html',
  styleUrl: './user-edit.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserEditComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly usersApi = inject(UserService);
  private readonly auth = inject(AuthService);
  private readonly snackbar = inject(SnackbarService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly userId = Number(this.route.snapshot.paramMap.get('id'));

  protected readonly roles = ROLE_OPTIONS;
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly inactivating = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly loadedUser = signal<AdminUser | null>(null);
  protected readonly confirming = signal<Confirmation | null>(null);
  protected readonly busy = computed(() => this.saving() || this.inactivating());
  protected readonly isSelf = computed(() => this.auth.currentUser?.id === this.loadedUser()?.id);
  protected readonly showsPendencies = computed(() => isClient(this.loadedUser()?.role_codes ?? []));

  protected readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, nonBlank, Validators.minLength(2), Validators.maxLength(150)]],
    email: ['', [Validators.required, emailFormat]],
    roleCode: ['' as RoleCode, Validators.required],
  });

  ngOnInit(): void {
    if (!Number.isInteger(this.userId) || this.userId <= 0) {
      this.loading.set(false);
      this.error.set('Identificador de usuário inválido.');
      return;
    }
    this.usersApi
      .get(this.userId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (user) => {
          this.applyUser(user);
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.detail || 'Não foi possível carregar o usuário.');
          this.loading.set(false);
        },
      });
  }

  protected summary(): string {
    const user = this.loadedUser();
    return user ? `${roleLabel(user.role_codes[0] ?? 'USER')} • ${user.is_active ? 'Ativo' : 'Inativo'}` : '';
  }

  protected nameError(): string | null {
    return fieldError(
      this.form.controls.name,
      {
        required: 'Informe o nome do usuário.',
        blank: 'Informe um nome com pelo menos 2 caracteres.',
        minlength: 'O nome precisa ter pelo menos 2 caracteres.',
        maxlength: 'O nome pode ter no máximo 150 caracteres.',
      },
      this.submitted(),
    );
  }

  protected emailError(): string | null {
    return fieldError(
      this.form.controls.email,
      {
        required: 'Informe o e-mail do usuário.',
        email: 'Digite um e-mail válido, no formato nome@dominio.com.',
      },
      this.submitted(),
    );
  }

  protected roleChangeText(): string {
    const user = this.loadedUser();
    const from = roleLabel(user?.role_codes[0] ?? 'USER');
    const to = roleLabel(this.form.controls.roleCode.value);
    return `O perfil de ${user?.name ?? 'este usuário'} passará de ${from} para ${to} e as permissões serão alteradas.`;
  }

  /** Valida o formulário; mudança de perfil pede confirmação antes de enviar. */
  protected submit(): void {
    if (this.busy() || this.loadedUser()?.is_active === false) return;
    this.submitted.set(true);
    const name = this.form.controls.name.value.trim();
    this.form.controls.name.setValue(name);
    if (this.form.invalid) {
      this.host.nativeElement.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
      return;
    }
    const originalRole = this.loadedUser()?.role_codes[0];
    if (originalRole && originalRole !== this.form.getRawValue().roleCode) {
      this.openConfirmation('role');
      return;
    }
    this.save();
  }

  protected askInactivation(): void {
    if (this.busy() || this.isSelf() || this.loadedUser()?.is_active !== true) return;
    this.openConfirmation('inactivate');
  }

  protected cancelConfirmation(): void {
    if (this.busy()) return;
    this.confirming.set(null);
  }

  protected confirmRoleChange(): void {
    if (this.busy()) return;
    this.save();
  }

  protected confirmInactivation(): void {
    const user = this.loadedUser();
    if (this.busy() || !user || !user.is_active || this.isSelf()) return;
    this.inactivating.set(true);
    this.error.set(null);
    this.usersApi
      .inactivate(user.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.applyUser({ ...user, ...updated });
          this.confirming.set(null);
          this.inactivating.set(false);
          this.snackbar.show(`${user.name} foi inativado com sucesso.`, 'success');
        },
        error: (error: ApiError) => {
          this.confirming.set(null);
          this.inactivating.set(false);
          this.snackbar.show(error.detail || 'Não foi possível inativar o usuário.', 'error');
        },
      });
  }

  protected back(): void {
    void this.router.navigate(['/gestao/usuarios']);
  }

  private save(): void {
    const { name, email, roleCode } = this.form.getRawValue();
    this.saving.set(true);
    this.error.set(null);
    this.usersApi
      .update(this.userId, { name: name.trim(), email: email.trim(), role_code: roleCode })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (user) => {
          this.applyUser(user);
          this.confirming.set(null);
          this.saving.set(false);
          this.submitted.set(false);
          this.snackbar.show('Usuário atualizado com sucesso.', 'success');
        },
        error: (error: ApiError) => {
          this.confirming.set(null);
          this.saving.set(false);
          this.snackbar.show(error.detail || 'Não foi possível atualizar o usuário.', 'error');
        },
      });
  }

  private applyUser(user: AdminUser): void {
    this.loadedUser.set(user);
    this.form.setValue({
      name: user.name,
      email: user.email,
      roleCode: (user.role_codes[0] ?? 'USER') as RoleCode,
    });
    if (!user.is_active) {
      this.form.disable();
    } else {
      this.form.enable();
      if (this.auth.currentUser?.id === user.id && user.role_codes.includes('ADMINISTRATOR')) {
        this.form.controls.roleCode.disable();
      }
    }
  }

  private openConfirmation(kind: Confirmation): void {
    this.confirming.set(kind);
    setTimeout(() => this.host.nativeElement.querySelector<HTMLElement>('.confirm-card')?.focus());
  }
}
