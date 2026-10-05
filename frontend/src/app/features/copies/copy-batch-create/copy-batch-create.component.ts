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
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { BookDetail } from '../../books/models/book.model';
import { BookService } from '../../books/services/book.service';
import { CopyResponse, DestinationType } from '../models/copy.model';
import { CopyService } from '../services/copy.service';

@Component({
  selector: 'app-copy-batch-create',
  standalone: true,
  imports: [RouterLink, ReactiveFormsModule, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './copy-batch-create.component.html',
  styleUrl: './copy-batch-create.component.scss',
})
export class CopyBatchCreateComponent {
  private readonly books = inject(BookService);
  private readonly copies = inject(CopyService);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly id = Number(this.route.snapshot.paramMap.get('id'));
  protected readonly book = signal<BookDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly queueError = signal<string | null>(null);
  protected readonly codes = signal<readonly string[]>([]);
  protected readonly scanner = signal('');
  protected readonly pasted = signal('');
  protected readonly quantity = signal(1);
  protected readonly mode = signal<'generate' | 'scan' | 'paste'>('generate');
  protected readonly created = signal<readonly CopyResponse[]>([]);
  protected readonly form = this.fb.nonNullable.group({
    destination: ['DIDACTIC', Validators.required],
    condition: ['', Validators.maxLength(30)],
    salePrice: [''],
    acquiredAt: [''],
  });
  constructor() {
    this.form.controls.destination.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        this.form.controls.salePrice.setValidators(
          value === 'COMMERCIAL'
            ? [
                Validators.required,
                Validators.min(0.01),
                Validators.pattern(/^\d{1,8}(?:\.\d{1,2})?$/),
              ]
            : [],
        );
        this.form.controls.salePrice.updateValueAndValidity({ emitEvent: false });
      });
    this.load();
  }
  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    if (!Number.isSafeInteger(this.id) || this.id <= 0) {
      this.loading.set(false);
      this.error.set('Obra inválida. Selecione uma obra no acervo.');
      return;
    }
    this.books
      .get(this.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (book) => {
          this.book.set(book);
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.detail);
          this.loading.set(false);
        },
      });
  }
  protected setMode(mode: 'generate' | 'scan' | 'paste'): void {
    this.mode.set(mode);
    this.queueError.set(null);
  }
  private add(values: readonly string[]): boolean {
    if (this.saving()) return false;
    this.queueError.set(null);
    const codes = values.map((code) => code.trim()).filter(Boolean);
    const existing = new Set([
      ...(this.book()?.copies.map((copy) => copy.barcode) ?? []),
      ...this.codes(),
    ]);
    if (!codes.length) {
      this.queueError.set('Informe pelo menos um código de exemplar.');
      return false;
    }
    if (codes.some((code) => code.length > 100)) {
      this.queueError.set('Cada código deve ter até 100 caracteres.');
      return false;
    }
    const duplicates = codes.filter(
      (code, index) => existing.has(code) || codes.indexOf(code) !== index,
    );
    if (duplicates.length) {
      this.queueError.set(
        'Códigos repetidos ou já cadastrados nesta obra: ' + [...new Set(duplicates)].join(', '),
      );
      return false;
    }
    this.codes.update((current) => [...current, ...codes]);
    return true;
  }
  protected generate(): void {
    const quantity = this.quantity();
    if (!Number.isSafeInteger(quantity) || quantity < 1 || quantity > 100) {
      this.queueError.set('Escolha de 1 a 100 códigos por geração.');
      return;
    }
    this.add(
      Array.from(
        { length: quantity },
        () => `LS-${this.id}-${crypto.randomUUID().replaceAll('-', '').toUpperCase()}`,
      ),
    );
  }
  protected scan(event?: Event): void {
    event?.preventDefault();
    if (this.add([this.scanner()])) this.scanner.set('');
    this.host.nativeElement.querySelector<HTMLElement>('#scan-code')?.focus();
  }
  protected paste(): void {
    if (this.add(this.pasted().split(/\r?\n/))) this.pasted.set('');
  }
  protected remove(index: number): void {
    if (!this.saving()) this.codes.update((codes) => codes.filter((_, i) => i !== index));
  }
  protected submit(): void {
    if (this.saving() || !this.book() || this.created().length) return;
    this.form.markAllAsTouched();
    this.error.set(null);
    if (!this.codes().length) {
      this.queueError.set('Prepare os códigos dos exemplares antes de cadastrar.');
      return;
    }
    if (this.form.invalid) {
      this.host.nativeElement.querySelector<HTMLElement>('.ng-invalid:not(form)')?.focus();
      return;
    }
    const value = this.form.getRawValue();
    this.saving.set(true);
    this.form.disable({ emitEvent: false });
    this.copies
      .createBatch(
        this.codes().map((barcode) => ({
          bookId: this.id,
          barcode,
          destination: value.destination as DestinationType,
          condition: value.condition.trim() || null,
          salePrice: value.destination === 'COMMERCIAL' ? Number(value.salePrice) : null,
          acquiredAt: value.acquiredAt || null,
        })),
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (copies) => {
          this.created.set(copies);
          this.saving.set(false);
          this.form.enable({ emitEvent: false });
        },
        error: (error: ApiError) => {
          this.saving.set(false);
          this.form.enable({ emitEvent: false });
          this.error.set(
            error.status === 409
              ? 'Um código deste lote já está cadastrado no acervo. Nenhum exemplar foi adicionado. Revise os códigos e tente novamente.'
              : error.detail,
          );
        },
      });
  }
  protected anotherBatch(): void {
    const created = this.created();
    this.book.update((book) =>
      book
        ? {
            ...book,
            copies: [
              ...book.copies,
              ...created.map((copy) => ({
                id: copy.id,
                book_id: copy.bookId,
                barcode: copy.barcode,
                destination: copy.destination,
                condition: copy.condition,
                sale_price: copy.salePrice,
                acquired_at: copy.acquiredAt,
                status: copy.status,
                is_active: copy.isActive,
              })),
            ],
          }
        : null,
    );
    this.created.set([]);
    this.codes.set([]);
    this.error.set(null);
    this.queueError.set(null);
  }
}
