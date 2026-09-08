import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AdminUser, RoleCode } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { emailFormat } from '../../../shared/validators/email.validator';
import { fieldError } from '../../../shared/validators/form-errors';

const ROLES: readonly { label: string; value: RoleCode }[] = [
  { label: 'Cliente', value: 'USER' },
  { label: 'Vendedor', value: 'SELLER' },
  { label: 'Estoquista', value: 'STOCK_KEEPER' },
  { label: 'Administrador', value: 'ADMINISTRATOR' },
];

function nonBlank(control: AbstractControl<string>): ValidationErrors | null {
  return control.value.trim().length === 0 ? { blank: true } : null;
}

@Component({
  selector: 'app-user-edit',
  standalone: true,
  imports: [ReactiveFormsModule, AlertComponent, SpinnerComponent],
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
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly userId = Number(this.route.snapshot.paramMap.get('id'));

  protected readonly roles = ROLES;
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly loadedUser = signal<AdminUser | null>(null);

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
          this.loadedUser.set(user);
          this.form.setValue({
            name: user.name,
            email: user.email,
            roleCode: (user.role_codes[0] ?? 'USER') as RoleCode,
          });
          if (this.auth.currentUser?.id === user.id && user.role_codes.includes('ADMINISTRATOR')) {
            this.form.controls.roleCode.disable();
          }
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.detail || 'Não foi possível carregar o usuário.');
          this.loading.set(false);
        },
      });
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

  protected submit(): void {
    if (this.saving()) return;
    this.submitted.set(true);
    const name = this.form.controls.name.value.trim();
    this.form.controls.name.setValue(name);
    if (this.form.invalid) {
      this.host.nativeElement.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
      return;
    }

    const originalRole = this.loadedUser()?.role_codes[0];
    const { email, roleCode } = this.form.getRawValue();
    if (originalRole && originalRole !== roleCode) {
      if (!window.confirm('Confirmar a alteração do cargo e das permissões deste usuário?')) return;
    }

    this.saving.set(true);
    this.error.set(null);
    this.success.set(null);
    this.usersApi
      .update(this.userId, { name, email: email.trim(), role_code: roleCode })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (user) => {
          this.loadedUser.set(user);
          this.success.set('Usuário atualizado com sucesso.');
          this.saving.set(false);
          this.submitted.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.detail || 'Não foi possível atualizar o usuário.');
          this.saving.set(false);
        },
      });
  }

  protected back(): void {
    void this.router.navigate(['/gestao/usuarios']);
  }
}
