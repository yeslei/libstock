import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

export type AlertVariant = 'error' | 'success' | 'info';

/**
 * Mensagem no nível do formulário (Nielsen #9).
 *
 * Erros usam `role="alert"` (assertivo — interrompe o leitor de tela, porque o
 * usuário acabou de agir e precisa saber que falhou); confirmações usam
 * `role="status"`, que aguarda uma pausa natural.
 */
@Component({
  selector: 'app-alert',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="alert"
      [class.alert--error]="variant === 'error'"
      [class.alert--success]="variant === 'success'"
      [class.alert--info]="variant === 'info'"
      [attr.role]="variant === 'error' ? 'alert' : 'status'"
      [attr.aria-live]="variant === 'error' ? 'assertive' : 'polite'"
    >
      <span class="alert__icon" aria-hidden="true">{{ icon }}</span>
      <div class="alert__body">
        <p class="alert__message">{{ message }}</p>
        <ng-content />
      </div>
    </div>
  `,
  styleUrl: './alert.component.scss',
})
export class AlertComponent {
  @Input({ required: true }) message = '';
  @Input() variant: AlertVariant = 'error';

  get icon(): string {
    switch (this.variant) {
      case 'success':
        return '✓';
      case 'info':
        return 'i';
      default:
        return '!';
    }
  }
}
