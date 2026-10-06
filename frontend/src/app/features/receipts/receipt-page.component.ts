import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { TokenStoreService } from '../../core/services/token-store.service';
import { ReceiptComponent } from './receipt.component';
import { ReceiptKind } from './receipt.service';

/**
 * Rota dedicada do comprovante (`/comprovantes/emprestimo|devolucao|venda/:id`). O guard exige funcionário
 * ou cliente; o backend decide o acesso final (funcionário ativo lê qualquer um, o cliente só os próprios,
 * e os alheios aparecem como "não encontrado"). Serve igualmente à reimpressão no balcão e no totem.
 */
@Component({
  selector: 'app-receipt-page',
  standalone: true,
  imports: [ReceiptComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="receipt-page">
      <a class="receipt-page__back" [routerLink]="backLink()">← {{ backLabel() }}</a>
      <h1 class="receipt-page__title" tabindex="-1">Comprovante</h1>
      <app-receipt [kind]="kind" [id]="id()" />
    </main>
  `,
  styles: `
    .receipt-page { max-width: 720px; margin: 0 auto; padding: 24px 16px; }
    .receipt-page__title { margin: 12px 0 0; font-size: 1.5rem; }
    .receipt-page__back { font-size: 0.875rem; }
  `,
})
export class ReceiptPageComponent {
  private readonly store = inject(TokenStoreService);
  protected readonly kind = inject(ActivatedRoute).snapshot.data['receipt'] as ReceiptKind;
  /** Parâmetro `:id` da rota (`withComponentInputBinding`). */
  readonly id = input.required<string>();

  private readonly staff = computed(() =>
    (this.store.user?.role_codes ?? []).some((role) => role === 'SELLER' || role === 'ADMINISTRATOR'),
  );
  protected readonly backLink = computed(() => (this.staff() ? '/balcao/painel' : '/meus-emprestimos'));
  protected readonly backLabel = computed(() => (this.staff() ? 'Voltar ao balcão' : 'Meus empréstimos'));
}
