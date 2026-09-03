import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiError, FormState } from '../../../core/models/auth.model';
import { AuthFormStateService } from '../../../core/services/auth-form-state.service';
import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PasswordFieldComponent,
} from '../../../shared/components/password-field/password-field.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { emailFormat } from '../../../shared/validators/email.validator';
import { fieldError } from '../../../shared/validators/form-errors';
import { matchPassword } from '../../../shared/validators/match-password.validator';

const NAME_ERRORS = {
  required: 'Informe seu nome.',
  minlength: 'O nome precisa ter pelo menos 2 caracteres.',
  maxlength: 'O nome pode ter no máximo 150 caracteres.',
};

const EMAIL_ERRORS = {
  required: 'Informe seu e-mail.',
  email: 'Digite um e-mail válido, no formato nome@dominio.com.',
};

const PASSWORD_ERRORS = {
  required: 'Crie uma senha.',
  minlength: `A senha precisa ter pelo menos ${PASSWORD_MIN_LENGTH} caracteres.`,
  maxlength: `A senha pode ter no máximo ${PASSWORD_MAX_LENGTH} caracteres.`,
};

const CONFIRMATION_ERRORS = {
  required: 'Repita a senha para confirmar.',
  passwordMismatch: 'As senhas não coincidem.',
};

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AlertComponent,
    PasswordFieldComponent,
    SpinnerComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly formState = inject(AuthFormStateService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);

  /**
   * Quatro campos e nada mais (Lei de Hick): "confirmar e-mail" adiciona
   * atrito sem ganho real — o erro de digitação aparece no primeiro login.
   * As regras espelham exatamente o `UserCreate` do backend; inventar
   * exigências de maiúscula ou símbolo criaria divergência de contrato.
   */
  protected readonly form = this.fb.nonNullable.group(
    {
      name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(150)]],
      email: [this.formState.lastEmail, [Validators.required, emailFormat]],
      password: [
        '',
        [
          Validators.required,
          Validators.minLength(PASSWORD_MIN_LENGTH),
          Validators.maxLength(PASSWORD_MAX_LENGTH),
        ],
      ],
      passwordConfirmation: ['', [Validators.required]],
    },
    { validators: matchPassword('password', 'passwordConfirmation') },
  );

  protected readonly state = signal<FormState>({ status: 'idle' });
  protected readonly submitted = signal(false);

  constructor() {
    this.form.controls.email.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((email) => this.formState.rememberEmail(email));
  }

  protected get isSubmitting(): boolean {
    return this.state().status === 'submitting';
  }

  protected get formError(): string | null {
    const state = this.state();
    return state.status === 'error' ? state.message : null;
  }

  protected get isDuplicateEmail(): boolean {
    const state = this.state();
    return state.status === 'error' && state.code === 'duplicate_email';
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

  protected confirmationError(): string | null {
    return fieldError(this.form.controls.passwordConfirmation, CONFIRMATION_ERRORS, this.submitted());
  }

  /**
   * O backend guarda o nome como `" ".join(value.split())`. Normalizar no blur
   * faz o usuário ver o valor final antes de enviar, em vez de descobrir a
   * mudança depois de criada a conta (Nielsen #1).
   */
  protected normalizeName(): void {
    const control = this.form.controls.name;
    const normalized = control.value.split(/\s+/).filter(Boolean).join(' ');
    if (normalized !== control.value) {
      control.setValue(normalized);
    }
  }

  protected submit(): void {
    this.submitted.set(true);
    this.normalizeName();

    if (this.form.invalid) {
      this.state.set({ status: 'idle' });
      this.focusFirstInvalid();
      return;
    }

    if (this.isSubmitting) {
      return;
    }

    this.state.set({ status: 'submitting' });
    const { name, email, password } = this.form.getRawValue();
    const normalizedEmail = email.trim();

    // O registro devolve 201 sem token — o login é uma segunda chamada.
    this.auth
      .register({ name, email: normalizedEmail, password })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.signInAfterRegister(normalizedEmail, password),
        error: (error: ApiError) => {
          this.state.set({ status: 'error', message: error.detail, code: error.code });
          if (error.code === 'duplicate_email' || error.status === 409) {
            this.focus('register-email');
          }
        },
      });
  }

  private signInAfterRegister(email: string, password: string): void {
    this.auth
      .login({ email, password })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.formState.clear();
          void this.router.navigateByUrl('/');
        },
        error: () => {
          // A conta existe; só a entrada automática falhou. Levar ao login com
          // o e-mail preservado é melhor do que anunciar um erro sem saída.
          this.formState.rememberEmail(email);
          this.formState.setFlash(
            'Conta criada! Entre com seu e-mail e senha para continuar.',
            'success',
          );
          void this.router.navigate(['/login']);
        },
      });
  }

  private focusFirstInvalid(): void {
    const order: [string, boolean][] = [
      ['register-name', this.form.controls.name.invalid],
      ['register-email', this.form.controls.email.invalid],
      ['register-password', this.form.controls.password.invalid],
      ['register-password-confirmation', this.form.controls.passwordConfirmation.invalid],
    ];

    const first = order.find(([, invalid]) => invalid);
    if (first) {
      this.focus(first[0]);
    }
  }

  private focus(id: string): void {
    this.host.nativeElement.querySelector<HTMLInputElement>(`#${id}`)?.focus();
  }
}
