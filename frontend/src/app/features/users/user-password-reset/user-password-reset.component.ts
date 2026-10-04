import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, Input, OnChanges, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ApiError } from '../../../core/models/auth.model';
import { AdminUser } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, PasswordFieldComponent } from '../../../shared/components/password-field/password-field.component';
import { SnackbarComponent } from '../../../shared/components/snackbar/snackbar.component';
import { SnackbarService } from '../../../shared/components/snackbar/snackbar.service';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { fieldError } from '../../../shared/validators/form-errors';
import { matchPassword } from '../../../shared/validators/match-password.validator';

@Component({
  selector: 'app-user-password-reset',
  standalone: true,
  imports: [ReactiveFormsModule, AlertComponent, PasswordFieldComponent, SnackbarComponent, SpinnerComponent],
  templateUrl: './user-password-reset.component.html',
  styleUrl: './user-password-reset.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserPasswordResetComponent implements OnChanges {
  @Input({ required: true }) user!: AdminUser;
  private readonly api = inject(UserService);
  private readonly snackbar = inject(SnackbarService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private focusTimer?: ReturnType<typeof setTimeout>;
  private version = 0;
  protected readonly step = signal<'closed' | 'form' | 'confirm' | 'uncertain'>('closed');
  protected readonly busy = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(PASSWORD_MIN_LENGTH), Validators.maxLength(PASSWORD_MAX_LENGTH)]],
    confirmation: ['', [Validators.required]],
  }, { validators: matchPassword('password', 'confirmation') });

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.version++;
      this.form.reset();
      clearTimeout(this.focusTimer);
    });
  }

  ngOnChanges(): void {
    this.version++;
    this.clear();
    this.busy.set(false);
    this.step.set('closed');
  }

  protected begin(): void {
    if (this.busy()) return;
    this.clear();
    this.step.set('form');
    this.focus('#reset-password');
  }

  protected cancel(): void {
    if (this.busy()) return;
    this.clear();
    this.step.set('closed');
    this.focus('[data-reset-open]');
  }

  protected passwordError(): string | null {
    return fieldError(this.form.controls.password, {
      required: 'Informe a nova senha.', minlength: 'A senha precisa ter pelo menos 8 caracteres.',
      maxlength: 'A senha pode ter no máximo 128 caracteres.',
    }, this.submitted());
  }

  protected confirmationError(): string | null {
    return fieldError(this.form.controls.confirmation, {
      required: 'Confirme a nova senha.', passwordMismatch: 'As senhas não coincidem.',
    }, this.submitted());
  }

  protected ask(): void {
    if (this.busy() || this.step() !== 'form') return;
    this.submitted.set(true);
    if (this.form.invalid) {
      this.focus('[aria-invalid="true"]');
      return;
    }
    this.step.set('confirm');
    this.focus('.confirm-card');
  }

  protected confirm(): void {
    if (this.busy() || this.step() !== 'confirm' || this.form.invalid) return;
    const version = this.version;
    this.busy.set(true);
    this.api.resetPassword(this.user.id, { new_password: this.form.controls.password.value })
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: () => {
          if (version !== this.version) return;
          this.busy.set(false);
          this.clear();
          this.step.set('closed');
          this.snackbar.show('Senha redefinida com sucesso.', 'success');
          this.focus('[data-reset-open]');
        },
        error: (error: ApiError) => {
          if (version !== this.version) return;
          this.busy.set(false);
          this.clear();
          if (!error.status || error.status >= 500) {
            this.step.set('uncertain');
            this.focus('[data-reset-uncertain]');
          } else {
            this.step.set('form');
            this.error.set(error.detail || 'Não foi possível redefinir a senha. Confira os dados e tente novamente.');
            this.focus('[data-reset-error]');
          }
        },
      });
  }

  private clear(): void {
    this.form.reset();
    this.submitted.set(false);
    this.error.set(null);
  }

  private focus(selector: string): void {
    clearTimeout(this.focusTimer);
    this.focusTimer = setTimeout(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus());
  }
}
