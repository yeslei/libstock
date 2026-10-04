import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, computed, effect, inject, input, output, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { toLoadState } from '../counter/desk-flow';
import { ReceiptView, toReceiptView } from './receipt-view';
import { AnyReceipt, ReceiptKind, ReceiptService } from './receipt.service';

const LOAD_ERROR = 'Não foi possível carregar o comprovante. Tente novamente.';

/**
 * Comprovante de empréstimo, devolução ou venda, montado só com os dados persistidos
 * (`GET /api/v1/receipts/...`) e, por isso, idêntico em toda reimpressão.
 * A impressão usa `window.print()` e o CSS de impressão global mostra apenas `.receipt`;
 * funciona igual no balcão e no totem (o navegador decide a impressora).
 */
@Component({
  selector: 'app-receipt',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './receipt.component.html',
  styleUrl: './receipt.component.scss',
})
export class ReceiptComponent {
  private readonly service = inject(ReceiptService);
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly kind = input.required<ReceiptKind>();
  /** Número do empréstimo (comprovantes de empréstimo e devolução) ou da venda. */
  readonly id = input.required<string | number>();
  /** Mostra "Fechar comprovante" quando o comprovante aparece dentro de outra tela. */
  readonly closable = input(false);
  /** Leva o foco ao título depois de carregar (comprovante recém-gerado). */
  readonly focusOnLoad = input(false);
  readonly closed = output<void>();

  private readonly retries = signal(0);
  private readonly request = computed(() => ({ kind: this.kind(), id: Number(this.id()), retry: this.retries() }));

  protected readonly state = toSignal(
    toObservable(this.request).pipe(
      switchMap(({ kind, id }) => toLoadState(this.service.get(kind, id), LOAD_ERROR)),
    ),
    { initialValue: { status: 'loading' } as LoadState<AnyReceipt> },
  );

  protected readonly view = computed<ReceiptView | null>(() => {
    const state = this.state();
    return state.status === 'loaded' ? toReceiptView(this.kind(), state.data) : null;
  });

  constructor() {
    effect(() => {
      if (this.view() && this.focusOnLoad()) {
        queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('h2')?.focus());
      }
    });
  }

  protected retry(): void {
    this.retries.update((value) => value + 1);
  }

  protected print(): void {
    this.document.defaultView?.print();
  }
}
