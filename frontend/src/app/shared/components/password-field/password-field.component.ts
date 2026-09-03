import { ChangeDetectionStrategy, Component, Input, computed, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;

interface Requirement {
  readonly label: string;
  readonly met: boolean;
}

@Component({
  selector: 'app-password-field',
  standalone: true,
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './password-field.component.html',
  styleUrl: './password-field.component.scss',
})
export class PasswordFieldComponent {
  @Input({ required: true }) control!: FormControl<string>;
  @Input({ required: true }) inputId = '';
  @Input() label = 'Senha';
  @Input() autocomplete: 'current-password' | 'new-password' = 'current-password';
  /** Mensagem já traduzida pelo componente-pai; `null` esconde o bloco de erro. */
  @Input() errorMessage: string | null = null;
  /**
   * Requisitos visíveis *antes* de digitar (Nielsen #5 — prevenir erro é melhor
   * do que explicá-lo depois). Só no cadastro: no login, exibir a política de
   * senha não ajuda quem já tem conta e ainda revela a regra sem necessidade.
   */
  @Input() showRequirements = false;

  protected readonly visible = signal(false);
  protected readonly value = signal('');

  protected readonly requirements = computed<Requirement[]>(() => {
    const length = this.value().length;
    return [
      {
        label: `Pelo menos ${PASSWORD_MIN_LENGTH} caracteres`,
        met: length >= PASSWORD_MIN_LENGTH,
      },
      {
        label: `No máximo ${PASSWORD_MAX_LENGTH} caracteres`,
        met: length <= PASSWORD_MAX_LENGTH,
      },
    ];
  });

  protected get describedBy(): string | null {
    const ids = [
      this.showRequirements ? `${this.inputId}-requirements` : null,
      this.errorMessage ? `${this.inputId}-error` : null,
    ].filter((id): id is string => id !== null);

    return ids.length > 0 ? ids.join(' ') : null;
  }

  protected toggleVisibility(): void {
    this.visible.update((current) => !current);
  }

  protected onInput(event: Event): void {
    this.value.set((event.target as HTMLInputElement).value);
  }
}
