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
import { RouterLink } from '@angular/router';

import { ApiError, FormState } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { fieldError } from '../../../shared/validators/form-errors';
import { BookCreateRequest, BookResponse } from '../models/book.model';
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

@Component({
  selector: 'app-book-create',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, AlertComponent, SpinnerComponent],
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
  });
  protected readonly state = signal<FormState>({ status: 'idle' });
  protected readonly submitted = signal(false);
  protected readonly createdBook = signal<BookResponse | null>(null);

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
    };
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
    this.state.set({ status: 'error', message: error.detail, code: error.code });
    if (error.code === 'duplicate_isbn' || error.code === 'google_books_not_found') {
      this.focus('book-isbn');
    }
  }

  private applyValidationErrors(error: ApiError): boolean {
    let applied = false;
    for (const issue of error.validationErrors ?? []) {
      if (issue.field && issue.field in this.form.controls) {
        const control = this.form.controls[issue.field as keyof typeof this.form.controls];
        control.setErrors({ ...(control.errors ?? {}), server: true });
        control.markAsTouched();
        applied = true;
      }
    }
    return applied;
  }

  private focusFirstInvalid(): void {
    const first = (['isbn', 'title', 'author', 'genre'] as const).find(
      (field) => this.form.controls[field].invalid,
    );
    if (first) {
      this.focus(`book-${first}`);
    }
  }

  private focus(id: string): void {
    this.host.nativeElement.querySelector<HTMLInputElement>(`#${id}`)?.focus();
  }
}
