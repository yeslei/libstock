import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';

import { ApiError, FormState } from '../../../core/models/auth.model';
import {
  CreateEmployeeResponse,
  EmployeeAccessLevel,
} from '../../../core/models/employee.model';
import { EmployeeService } from '../../../core/services/employee.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PasswordFieldComponent,
} from '../../../shared/components/password-field/password-field.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { emailFormat } from '../../../shared/validators/email.validator';
import { fieldError } from '../../../shared/validators/form-errors';

interface AccessLevelOption {
  readonly label: string;
  readonly value: EmployeeAccessLevel;
}

const ACCESS_LEVELS: readonly AccessLevelOption[] = [
  { label: 'Atendente', value: 'ATTENDANT' },
  { label: 'Vendedor', value: 'SELLER' },
  { label: 'Estoquista', value: 'STOCK_KEEPER' },
  { label: 'Gerente', value: 'MANAGER' },
];

const NAME_ERRORS = {
  required: 'Informe o nome do funcionário.',
  blank: 'Informe um nome com pelo menos 2 caracteres.',
  minlength: 'O nome precisa ter pelo menos 2 caracteres.',
  maxlength: 'O nome pode ter no máximo 150 caracteres.',
};

const EMAIL_ERRORS = {
  required: 'Informe o e-mail do funcionário.',
  email: 'Digite um e-mail válido, no formato nome@dominio.com.',
};

const PASSWORD_ERRORS = {
  required: 'Informe uma senha provisória.',
  minlength: `A senha precisa ter pelo menos ${PASSWORD_MIN_LENGTH} caracteres.`,
  maxlength: `A senha pode ter no máximo ${PASSWORD_MAX_LENGTH} caracteres.`,
};

const ACCESS_LEVEL_ERRORS = {
  required: 'Selecione um nível de acesso.',
  invalidAccessLevel: 'Selecione um nível de acesso válido.',
};

function nonBlank(control: AbstractControl<string>): ValidationErrors | null {
  return control.value.trim().length === 0 ? { blank: true } : null;
}

function validAccessLevel(control: AbstractControl<string>): ValidationErrors | null {
  const value = control.value;
  return ACCESS_LEVELS.some((option) => option.value === value)
    ? null
    : { invalidAccessLevel: true };
}

function toEmployeeErrorMessage(error: ApiError): string {
  if (error.status === 400) {
    return 'Confira os dados informados e tente novamente.';
  }

  if (error.status === 403) {
    return 'Você não tem permissão para cadastrar funcionários.';
  }

  if (error.status === 409 && error.code === 'duplicate_email') {
    return 'Este e-mail já está cadastrado.';
  }

  if (error.status === 409 && error.code === 'duplicate_employee_code') {
    return 'Não foi possível gerar um código único para o funcionário. Tente novamente.';
  }

  if (error.status === 422) {
    return error.detail || 'Confira os campos destacados e tente novamente.';
  }

  return error.detail || 'Não foi possível cadastrar o funcionário. Tente novamente.';
}

@Component({
  selector: 'app-create-employee',
  standalone: true,
  imports: [ReactiveFormsModule, AlertComponent, PasswordFieldComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './create-employee.component.html',
  styleUrl: './create-employee.component.scss',
})
export class CreateEmployeeComponent {
  private readonly fb = inject(FormBuilder);
  private readonly employees = inject(EmployeeService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly accessLevels = ACCESS_LEVELS;
  protected readonly state = signal<FormState>({ status: 'idle' });
  protected readonly submitted = signal(false);
  protected readonly createdEmployee = signal<CreateEmployeeResponse | null>(null);

  protected readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, nonBlank, Validators.minLength(2), Validators.maxLength(150)]],
    email: ['', [Validators.required, emailFormat]],
    password: [
      '',
      [
        Validators.required,
        Validators.minLength(PASSWORD_MIN_LENGTH),
        Validators.maxLength(PASSWORD_MAX_LENGTH),
      ],
    ],
    accessLevel: ['', [Validators.required, validAccessLevel]],
  });

  protected get isSubmitting(): boolean {
    return this.state().status === 'submitting';
  }

  protected get formError(): string | null {
    const state = this.state();
    return state.status === 'error' ? state.message : null;
  }

  protected get successMessage(): string | null {
    const state = this.state();
    return state.status === 'success' ? state.message : null;
  }

  protected nameError(): string | null {
    return fieldError(this.form.controls.name, NAME_ERRORS, this.submitted());
  }

  protected emailError(): string | null {
    return fieldError(this.form.controls.email, EMAIL_ERRORS, this.submitted());
  }

  protected passwordError(): string | null {
    return fieldError(this.form.controls.password, PASSWORD_ERRORS, this.submitted());
  }

  protected accessLevelError(): string | null {
    return fieldError(this.form.controls.accessLevel, ACCESS_LEVEL_ERRORS, this.submitted());
  }

  protected normalizeName(): void {
    const control = this.form.controls.name;
    const normalized = control.value.trim();
    if (normalized !== control.value) {
      control.setValue(normalized);
    }
  }

  protected submit(): void {
    if (this.isSubmitting) {
      return;
    }

    this.submitted.set(true);
    this.normalizeName();

    if (this.form.invalid) {
      this.state.set({ status: 'idle' });
      this.focusFirstInvalid();
      return;
    }

    this.state.set({ status: 'submitting' });
    this.createdEmployee.set(null);

    const { name, email, password, accessLevel } = this.form.getRawValue();

    this.employees
      .create({
        name,
        email: email.trim(),
        password,
        accessLevel: accessLevel as EmployeeAccessLevel,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (employee) => {
          this.createdEmployee.set(employee);
          this.state.set({
            status: 'success',
            message: 'Funcionário cadastrado com sucesso.',
          });
          this.form.reset();
          this.submitted.set(false);
        },
        error: (error: ApiError) => {
          this.state.set({
            status: 'error',
            message: toEmployeeErrorMessage(error),
            code: error.code,
          });
          this.focus('employee-form-feedback');
        },
      });
  }

  private focusFirstInvalid(): void {
    const order: [string, boolean][] = [
      ['employee-name', this.form.controls.name.invalid],
      ['employee-email', this.form.controls.email.invalid],
      ['employee-password', this.form.controls.password.invalid],
      ['employee-access-level', this.form.controls.accessLevel.invalid],
    ];

    const first = order.find(([, invalid]) => invalid);
    if (first) {
      this.focus(first[0]);
    }
  }

  private focus(id: string): void {
    this.host.nativeElement.querySelector<HTMLElement>(`#${id}`)?.focus();
  }
}
