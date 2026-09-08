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
import { catchError, debounceTime, filter, map, of, switchMap, tap } from 'rxjs';

import { ApiError, FormState } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { fieldError } from '../../../shared/validators/form-errors';
import { BookCreateRequest, BookMetadata, BookResponse } from '../models/book.model';
import { BookService } from '../services/book.service';
import { compactIsbn, isbnValidator } from '../validators/isbn.validator';

const ISBN_ERRORS = {
  required: 'Informe o ISBN.',
  isbn: 'Digite um ISBN-10 ou ISBN-13 válido, com o checksum correto.',
  server: 'O backend rejeitou este ISBN. Confira o valor informado.',
};
const TITLE_ERRORS = {
  maxlength: 'O título pode ter no máximo 255 caracteres.',
  server: 'Confira o título informado.',
};
const AUTHOR_ERRORS = {
  maxlength: 'O autor pode ter no máximo 255 caracteres.',
  server: 'Confira o autor informado.',
};
const GENRE_ERRORS = {
  maxlength: 'O gênero pode ter no máximo 100 caracteres.',
  server: 'Confira o gênero informado.',
};
const BARCODE_ERRORS = {
  required: 'Informe o código de barras do exemplar.',
  maxlength: 'O código de barras pode ter no máximo 100 caracteres.',
  server: 'Confira o código de barras informado.',
};
const CONDITION_ERRORS = {
  maxlength: 'A condição pode ter no máximo 30 caracteres.',
  server: 'Confira a condição informada.',
};
const PRICE_ERRORS = {
  required: 'Informe o preço do exemplar comercial.',
  min: 'O preço não pode ser negativo.',
  server: 'Confira o preço informado.',
};

@Component({
  selector: 'app-book-create',
  standalone: true,
  imports: [ReactiveFormsModule, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './book-create.component.html',
  styleUrl: './book-create.component.scss',
})
export class BookCreateComponent {
  private readonly fb = inject(FormBuilder);
  private readonly books = inject(BookService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly form = this.fb.nonNullable.group({
    isbn: ['', [Validators.required, isbnValidator]],
    title: ['', [Validators.maxLength(255)]],
    author: ['', [Validators.maxLength(255)]],
    genre: ['', [Validators.maxLength(100)]],
    coverUrl: ['', [Validators.pattern(/^https?:\/\/.+/i)]],
    barcode: ['', [Validators.required, Validators.maxLength(100)]],
    destination: ['DIDACTIC' as 'DIDACTIC' | 'COMMERCIAL', [Validators.required]],
    condition: ['', [Validators.maxLength(30)]],
    salePrice: this.fb.control<number | null>(null, [Validators.min(0)]),
    acquiredAt: [''],
  });
  protected readonly state = signal<FormState>({ status: 'idle' });
  protected readonly submitted = signal(false);
  protected readonly createdBook = signal<BookResponse | null>(null);
  protected readonly imageFailed = signal(false);
  protected readonly metadataState = signal<'idle' | 'loading' | 'loaded' | 'error'>('idle');
  protected readonly metadataMessage = signal<string | null>(null);
  protected readonly metadataLocked = signal(false);

  constructor() {
    this.form.controls.isbn.valueChanges
      .pipe(
        tap(() => this.unlockMetadata()),
        debounceTime(450),
        filter(() => this.form.controls.isbn.valid),
        map((isbn) => compactIsbn(isbn)),
        tap(() => {
          this.metadataState.set('loading');
          this.metadataMessage.set('Consultando dados da obra…');
        }),
        switchMap((isbn) =>
          this.books.lookupMetadata(isbn).pipe(
            map((metadata) => ({ metadata, error: null as ApiError | null })),
            catchError((error: ApiError) => of({ metadata: null as BookMetadata | null, error })),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ metadata, error }) => {
        if (metadata) {
          this.applyMetadata(metadata);
          return;
        }
        this.metadataState.set('error');
        this.metadataMessage.set(
          error?.status === 404
            ? 'ISBN não encontrado. Preencha título e autor manualmente.'
            : 'Não foi possível consultar agora. Preencha título e autor manualmente.',
        );
      });
  }

  protected get isSubmitting(): boolean {
    return this.state().status === 'submitting';
  }

  protected get formError(): string | null {
    const state = this.state();
    return state.status === 'error' ? state.message : null;
  }

  protected isbnError(): string | null {
    return fieldError(this.form.controls.isbn, ISBN_ERRORS, this.submitted());
  }

  protected titleError(): string | null {
    return fieldError(this.form.controls.title, TITLE_ERRORS, this.submitted());
  }

  protected authorError(): string | null {
    return fieldError(this.form.controls.author, AUTHOR_ERRORS, this.submitted());
  }

  protected genreError(): string | null {
    return fieldError(this.form.controls.genre, GENRE_ERRORS, this.submitted());
  }

  protected barcodeError(): string | null {
    return fieldError(this.form.controls.barcode, BARCODE_ERRORS, this.submitted());
  }

  protected conditionError(): string | null {
    return fieldError(this.form.controls.condition, CONDITION_ERRORS, this.submitted());
  }

  protected priceError(): string | null {
    return fieldError(this.form.controls.salePrice, PRICE_ERRORS, this.submitted());
  }

  protected destinationChanged(): void {
    const price = this.form.controls.salePrice;
    if (this.form.controls.destination.value === 'COMMERCIAL') {
      price.addValidators(Validators.required);
    } else {
      price.removeValidators(Validators.required);
      price.setValue(null);
    }
    price.updateValueAndValidity();
  }

  protected submit(): void {
    if (this.isSubmitting) {
      return;
    }
    this.submitted.set(true);
    this.createdBook.set(null);

    if (this.form.invalid) {
      this.state.set({ status: 'idle' });
      this.focusFirstInvalid();
      return;
    }

    this.state.set({ status: 'submitting' });
    this.books
      .create(this.payload())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (book) => {
          this.createdBook.set(book);
          this.state.set({ status: 'success', message: 'Obra cadastrada com sucesso.' });
          this.unlockMetadata(false);
          this.form.reset();
          this.submitted.set(false);
        },
        error: (error: ApiError) => this.handleError(error),
      });
  }

  private payload(): BookCreateRequest {
    const value = this.form.getRawValue();
    const optional = (text: string): string | null => text.trim() || null;
    return {
      isbn: compactIsbn(value.isbn),
      title: optional(value.title),
      author: optional(value.author),
      genre: optional(value.genre),
      cover_url: optional(value.coverUrl),
      initial_copy: {
        barcode: value.barcode.trim(),
        destination: value.destination,
        condition: optional(value.condition),
        sale_price: value.destination === 'COMMERCIAL' ? value.salePrice : null,
        acquired_at: optional(value.acquiredAt),
      },
    };
  }

  private applyMetadata(metadata: BookMetadata): void {
    this.form.patchValue({ title: metadata.title, author: metadata.author, genre: metadata.genre ?? '' });
    this.form.controls.title.disable();
    this.form.controls.author.disable();
    this.form.controls.genre.disable();
    this.metadataLocked.set(true);
    this.metadataState.set('loaded');
    this.metadataMessage.set('Dados preenchidos pelo Google Books e bloqueados para evitar inconsistências.');
  }

  private unlockMetadata(clearLockedValues = true): void {
    if (this.metadataLocked() && clearLockedValues) {
      this.form.patchValue({ title: '', author: '', genre: '' }, { emitEvent: false });
    }
    this.form.controls.title.enable({ emitEvent: false });
    this.form.controls.author.enable({ emitEvent: false });
    this.form.controls.genre.enable({ emitEvent: false });
    this.metadataLocked.set(false);
    this.metadataState.set('idle');
    this.metadataMessage.set(null);
  }

  private handleError(error: ApiError): void {
    if (error.status === 422 && this.applyValidationErrors(error)) {
      this.state.set({
        status: 'error',
        message: 'Confira os campos destacados e tente novamente.',
      });
      this.focusFirstInvalid();
      return;
    }
    const message = error.status === 503
      ? `${error.detail} Preencha título e autor manualmente para continuar o cadastro.`
      : error.detail;
    this.state.set({ status: 'error', message, code: error.code });
    if (error.code === 'duplicate_isbn' || error.code === 'google_books_not_found') {
      this.focus('book-isbn');
    } else if (error.code === 'duplicate_barcode') {
      this.focus('book-barcode');
    }
  }

  private applyValidationErrors(error: ApiError): boolean {
    let applied = false;
    for (const issue of error.validationErrors ?? []) {
      const field = issue.field?.replace('initial_copy.', '').replace('sale_price', 'salePrice');
      if (field && field in this.form.controls) {
        const control = this.form.controls[field as keyof typeof this.form.controls];
        control.setErrors({ ...(control.errors ?? {}), server: true });
        control.markAsTouched();
        applied = true;
      }
    }
    return applied;
  }

  private focusFirstInvalid(): void {
    const first = (['isbn', 'title', 'author', 'genre', 'coverUrl', 'barcode', 'destination', 'condition', 'salePrice', 'acquiredAt'] as const).find(
      (field) => this.form.controls[field].invalid,
    );
    if (first) {
      const ids: Partial<Record<typeof first, string>> = { salePrice: 'book-sale-price', acquiredAt: 'book-acquired-at' };
      this.focus(ids[first] ?? `book-${first}`);
    }
  }

  private focus(id: string): void {
    this.host.nativeElement.querySelector<HTMLInputElement>(`#${id}`)?.focus();
  }
}
