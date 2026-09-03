import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

/**
 * Indicador de progresso puramente decorativo: quem anuncia o estado ao leitor
 * de tela é o `aria-busy` do botão que o contém (Nielsen #1).
 */
@Component({
  selector: 'app-spinner',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="spinner" [style.--spinner-size.px]="size" aria-hidden="true"></span>`,
  styleUrl: './spinner.component.scss',
})
export class SpinnerComponent {
  @Input() size = 18;
}
