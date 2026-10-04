import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { SaveFailureComponent } from './save-failure.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { COPY_LOOKUP_LIMIT, CopyStatus, CounterService, StaffCopyLookup } from './counter.service';
import { ActionFlow, formatPrice, toLoadState } from './desk-flow';
import { ReceiptComponent } from '../receipts/receipt.component';

const UNAVAILABLE_REASON: Readonly<Record<CopyStatus, string>> = {
  AVAILABLE: 'venda em andamento ou reservado para um cliente',
  BORROWED: 'emprestado',
  RESERVED: 'reservado',
  SOLD: 'vendido',
  INACTIVE: 'inativo',
};

/**
 * Frame "Funcionário / Venda": localiza o exemplar por código, ISBN ou título (`GET /staff/copies`) e registra
 * a venda direta por `POST /api/v1/sales/`. A venda é confirmada no ato (pagamento no balcão) e o exemplar
 * passa a Vendido na mesma transação; o preço é sempre o cadastrado no exemplar (a tela não o envia nem edita).
 */
@Component({
  selector: 'app-counter-sales',
  standalone: true,
  imports: [SaveFailureComponent, AlertComponent, SpinnerComponent, ConfirmDialogComponent, ReceiptComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-sales.component.html',
  styleUrl: './counter-sales.component.scss',
})
export class CounterSalesComponent {
  private readonly service = inject(CounterService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly searches = new Subject<void>();

  protected readonly price = formatPrice;
  protected readonly limit = COPY_LOOKUP_LIMIT;
  protected readonly term = signal('');
  /** Termo da última busca enviada; é ele que a recarga reutiliza. */
  protected readonly searched = signal('');
  protected readonly missingTerm = signal(false);
  /** Venda recém-registrada; abre o comprovante de venda. */
  protected readonly soldId = signal<number | null>(null);
  /** `null` até a primeira busca. */
  protected readonly state = signal<LoadState<readonly StaffCopyLookup[]> | null>(null);

  protected readonly flow = new ActionFlow(inject(DestroyRef), () => {
    this.reload();
    queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('[data-feedback]')?.focus());
  });

  constructor() {
    this.searches
      .pipe(
        switchMap(() =>
          toLoadState(this.service.lookupCopies(this.searched()), 'Não foi possível buscar os exemplares. Tente novamente.'),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
    this.missingTerm.set(false);
  }

  protected search(event: Event): void {
    event.preventDefault();
    const term = this.term().trim();
    if (!term) {
      this.missingTerm.set(true);
      return;
    }
    this.flow.saveFailed.set(false);
    this.searched.set(term);
    this.reload();
  }

  protected reload(): void {
    if (this.searched()) this.searches.next();
  }

  protected unavailableReason(copy: StaffCopyLookup): string {
    return UNAVAILABLE_REASON[copy.status];
  }

  /** Só há venda com o preço cadastrado; o backend recusa exemplar comercial sem preço (`copy_without_price`). */
  protected canRegister(copy: StaffCopyLookup): boolean {
    return copy.sellable && copy.sale_price !== null && copy.sale_price !== '';
  }

  protected registerSale(copy: StaffCopyLookup): void {
    if (!this.canRegister(copy)) return;
    this.flow.ask({
      title: 'Registrar venda?',
      details: [
        `Obra: ${copy.book.title}`,
        `Exemplar: ${copy.barcode}`,
        `Preço: ${formatPrice(copy.sale_price)}`,
        'A venda será confirmada no ato e o exemplar ficará vendido.',
      ],
      confirmLabel: 'Registrar venda',
      run: () => this.service.registerSale(copy.id),
      success: (sale) =>
        `Venda registrada: “${copy.book.title}”, exemplar ${copy.barcode} vendido. Total ${formatPrice(sale.total_amount)} (venda nº ${sale.id}).`,
      done: (sale) => this.soldId.set(sale.id),
    });
  }
}
