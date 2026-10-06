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
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiError, FormState } from '../../../core/models/auth.model';
import { AuthFormStateService } from '../../../core/services/auth-form-state.service';
import { AuthService } from '../../../core/services/auth.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { PasswordFieldComponent } from '../../../shared/components/password-field/password-field.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { emailFormat } from '../../../shared/validators/email.validator';
import { fieldError } from '../../../shared/validators/form-errors';

const EMAIL_ERRORS = {
  required: 'Informe seu e-mail.',
  email: 'Digite um e-mail válido, no formato nome@dominio.com.',
};

const PASSWORD_ERRORS = {
  required: 'Informe sua senha.',
};

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AlertComponent,
    PasswordFieldComponent,
    SpinnerComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly formState = inject(AuthFormStateService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);

  /**
   * A senha valida apenas "não vazio" — o backend aceita `min_length=1` no
   * login. Exigir 8 caracteres aqui quebraria contas antigas e ainda revelaria
   * a política de senha a quem nem tem cadastro.
   */
  protected readonly form = this.fb.nonNullable.group({
    email: [this.formState.lastEmail, [Validators.required, emailFormat]],
    password: ['', [Validators.required]],
  });

  protected readonly state = signal<FormState>({ status: 'idle' });
  protected readonly submitted = signal(false);
  protected readonly notice = signal(this.formState.consumeFlash());

  constructor() {
    // Mantém o e-mail disponível para a tela de registro sem passá-lo pela URL.
    this.form.controls.email.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((email) => this.formState.rememberEmail(email));

    if (this.route.snapshot.queryParamMap.has('sessionExpired')) {
      this.notice.set({
        message: 'Sua sessão expirou. Entre novamente para continuar.',
        variant: 'info',
      });
    }
  }

  protected get isSubmitting(): boolean {
    return this.state().status === 'submitting';
  }

  protected get formError(): string | null {
    const state = this.state();
    return state.status === 'error' ? state.message : null;
  }

  protected emailError(): string | null {
    return fieldError(this.form.controls.email, EMAIL_ERRORS, this.submitted());
  }

  protected passwordError(): string | null {
    return fieldError(this.form.controls.password, PASSWORD_ERRORS, this.submitted());
  }

  protected submit(): void {
    this.submitted.set(true);
    this.notice.set(null);

    if (this.form.invalid) {
      this.state.set({ status: 'idle' });
      this.focusFirstInvalid();
      return;
    }

    if (this.isSubmitting) {
      return;
    }

    this.state.set({ status: 'submitting' });
    const { email, password } = this.form.getRawValue();

    this.auth
      .login({ email: email.trim(), password })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.formState.clear();
          void this.router.navigateByUrl(this.redirectTarget());
        },
        error: (error: ApiError) => {
          // Mensagem deliberadamente genérica: dizer qual campo está errado
          // transformaria a tela em um verificador de e-mails cadastrados.
          this.state.set({ status: 'error', message: error.detail, code: error.code });
          this.focus('login-password');
        },
      });
  }

  private redirectTarget(): string {
    const redirectTo = this.route.snapshot.queryParamMap.get('redirectTo');
    // Só caminhos internos: um `redirectTo` absoluto seria um open redirect.
    return redirectTo?.startsWith('/') && !redirectTo.startsWith('//') ? redirectTo : '/';
  }

  private focusFirstInvalid(): void {
    const id = this.form.controls.email.invalid ? 'login-email' : 'login-password';
    this.focus(id);
  }

  private focus(id: string): void {
    this.host.nativeElement.querySelector<HTMLInputElement>(`#${id}`)?.focus();
  }
}
