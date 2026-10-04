import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, map, merge, switchMap } from 'rxjs';

import { ApiError } from '../../core/models/auth.model';
import { LoadState } from '../../core/models/load-state.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SnackbarService } from '../../shared/components/snackbar/snackbar.service';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { CopyResponse, DestinationType } from '../copies/models/copy.model';
import { CopyService } from '../copies/services/copy.service';
import { CounterService, StaffCatalogBookDetail } from './counter.service';
import { destinationLabel, toLoadState } from './desk-flow';
import { SaveFailureComponent } from './save-failure.component';
import { failureVariant, isPersistenceFailure } from './save-failure';

/** Papéis que o backend autoriza em `POST /api/v1/copies/` (Issue #151: o vendedor administra o acervo). */
const CREATE_ROLES = ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'];
const BARCODE_MAX = 100;
const PRICE_PATTERN = /^\d+(?:\.\d{1,2})?$/;

interface Included {
  readonly copy: CopyResponse;
  readonly before: number;
  /** Quantidade informada pelo backend depois da inclusão; ausente se a recarga falhou. */
  readonly after: number | null;
}

/**
 * Frames "Complementos V2 · 03 Inclusão de exemplar": novo exemplar, código já usado e exemplar incluído.
 * Usa o endpoint existente de exemplares; o status inicial é definido pelo backend.
 */
@Component({
  selector: 'app-counter-copy-create',
  standalone: true,
  imports: [RouterLink, AlertComponent, SaveFailureComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-copy-create.component.html',
  styleUrl: './counter-catalog.component.scss',
})
export class CounterCopyCreateComponent {
  private readonly counter = inject(CounterService);
  private readonly copies = inject(CopyService);
  private readonly route = inject(ActivatedRoute);
  private readonly snackbar = inject(SnackbarService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly reloads = new Subject<void>();
  private currentId = 0;

  protected readonly canCreate = (inject(TokenStoreService).user?.role_codes ?? []).some((role) => CREATE_ROLES.includes(role));
  protected readonly state = signal<LoadState<StaffCatalogBookDetail>>({ status: 'loading' });
  protected readonly barcode = signal('');
  protected readonly destination = signal<DestinationType | ''>('');
  protected readonly price = signal('');
  protected readonly submitted = signal(false);
  protected readonly submitting = signal(false);
  protected readonly duplicateOf = signal<string | null>(null);
  protected readonly saveFailed = signal(false);
  protected readonly included = signal<Included | null>(null);
  protected readonly destinationLabel = destinationLabel;

  protected readonly duplicateShown = computed(() => this.duplicateOf() !== null && this.barcode().trim() === this.duplicateOf());
  protected readonly barcodeError = computed(() => {
    const value = this.barcode().trim();
    if (this.duplicateShown()) return 'Este código já está cadastrado. Informe outro código para continuar.';
    if (value.length > BARCODE_MAX) return `O código pode ter no máximo ${BARCODE_MAX} caracteres.`;
    if (this.submitted() && !value) return 'Informe o código do exemplar.';
    return null;
  });
  protected readonly destinationError = computed(() =>
    this.submitted() && !this.destination() ? 'Escolha a finalidade do exemplar.' : null);
  protected readonly priceError = computed(() => {
    if (this.destination() !== 'COMMERCIAL') return null;
    const value = this.normalizedPrice();
    if (!value) return this.submitted() ? 'Informe o preço de venda.' : null;
    if (!PRICE_PATTERN.test(value) || value.replace('.', '').length > 10) {
      return 'Informe um preço não negativo, com até 10 dígitos e duas casas decimais.';
    }
    return null;
  });

  constructor() {
    merge(
      this.route.paramMap.pipe(map((params) => (this.currentId = Number(params.get('id'))))),
      this.reloads.pipe(map(() => this.currentId)),
    )
      .pipe(
        switchMap((id) => toLoadState(this.counter.getCatalogBook(id), 'Não foi possível carregar a obra.')),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => {
        this.state.set(state);
        const done = this.included();
        if (done && done.after === null && state.status === 'loaded') {
          this.included.set({ ...done, after: state.data.total_copies });
        }
      });
  }

  protected reload(): void {
    this.reloads.next();
  }

  protected setBarcode(event: Event): void {
    this.barcode.set((event.target as HTMLInputElement).value);
  }

  protected setDestination(event: Event): void {
    this.destination.set((event.target as HTMLSelectElement).value as DestinationType | '');
  }

  protected setPrice(event: Event): void {
    this.price.set((event.target as HTMLInputElement).value);
  }

  protected submit(book: StaffCatalogBookDetail): void {
    if (this.submitting() || !this.canCreate || !book.is_active) return;
    this.submitted.set(true);
    this.saveFailed.set(false);
    const destination = this.destination();
    const code = this.barcode().trim();
    if (!destination || !code || this.barcodeError() || this.priceError()) return;
    if (destination === 'COMMERCIAL' && !this.normalizedPrice()) return;
    this.submitting.set(true);
    this.copies
      .create({
        bookId: book.id,
        barcode: code,
        destination,
        condition: null,
        salePrice: destination === 'COMMERCIAL' ? Number(this.normalizedPrice()) : null,
        acquiredAt: null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (copy) => {
          this.submitting.set(false);
          this.included.set({ copy, before: book.total_copies, after: null });
          this.reload();
        },
        error: (error: ApiError) => {
          this.submitting.set(false);
          if (error.status === 409) this.duplicateOf.set(code);
          else if (isPersistenceFailure(error)) this.saveFailed.set(true);
          else this.snackbar.show(this.messageFor(error), failureVariant(error));
        },
      });
  }

  protected addAnother(): void {
    this.included.set(null);
    this.barcode.set('');
    this.destination.set('');
    this.price.set('');
    this.submitted.set(false);
    this.duplicateOf.set(null);
    this.saveFailed.set(false);
  }

  private normalizedPrice(): string {
    return this.price().trim().replace(',', '.');
  }

  private messageFor(error: ApiError): string {
    if (error.status === 404) return 'A obra não foi encontrada ou está inativa.';
    if (error.status === 422) return 'Confira os dados informados e tente novamente.';
    return error.detail || 'Não foi possível cadastrar o exemplar. Tente novamente.';
  }
}
