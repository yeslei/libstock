import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

import { SAVE_FAILURE_TEXT } from './save-failure';

/**
 * Estado "Não foi possível salvar" (Complementos V2, seção 07). As ações (atualizar consulta, voltar) vêm
 * por projeção: a operação nunca é reenviada automaticamente.
 */
@Component({
  selector: 'app-save-failure',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="save-failure" role="alert" data-feedback tabindex="-1" aria-labelledby="save-failure-title">
      <h2 id="save-failure-title">Não foi possível salvar</h2>
      <div class="save-failure__box">
        <p><strong>A operação não foi concluída</strong></p>
        <p>{{ message }}</p>
      </div>
      <div class="save-failure__actions"><ng-content /></div>
    </section>
  `,
  styles: `
    .save-failure { margin: 16px 0; }
    .save-failure h2 { margin: 0 0 8px; }
    .save-failure__box { padding: 12px 16px; border-radius: 8px; background: #fae8e5; color: #3b1511; }
    .save-failure__box p { margin: 4px 0; }
    .save-failure__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  `,
})
export class SaveFailureComponent {
  @Input() message = SAVE_FAILURE_TEXT;
}
