import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnInit,
  Output,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { BookResponse, BookUpdateRequest } from '../models/book.model';
import { BookService } from '../services/book.service';
import { isbnValidator } from '../validators/isbn.validator';

export interface ToastMessage {
  type: 'success' | 'error';
  text: string;
}

@Component({
  selector: 'app-book-edit-modal',
  standalone: true,
  imports: [ReactiveFormsModule, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './book-edit-modal.component.html',
  styleUrl: './book-edit-modal.component.scss',
})
export class BookEditModalComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly bookService = inject(BookService);
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) book!: BookResponse;
  @Output() saved = new EventEmitter<BookResponse>();
  @Output() cancelled = new EventEmitter<void>();

  protected readonly state = signal<'idle' | 'submitting' | 'success' | 'error'>('idle');
  protected readonly toast = signal<ToastMessage | null>(null);
  protected readonly submitted = signal(false);

  protected readonly form = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(255)]],
    author: ['', [Validators.required, Validators.maxLength(255)]],
    genre: ['', [Validators.maxLength(100)]],
    isbn: ['', [isbnValidator]],
    publicationYear: [null as number | null, [Validators.min(1000), Validators.max(2100)]],
    publisher: ['', [Validators.maxLength(150)]],
    edition: ['', [Validators.maxLength(50)]],
    coverUrl: [''],
    isActive: [true],
  });

  ngOnInit(): void {
    if (this.book) {
      this.form.patchValue({
        title: this.book.title ?? '',
        author: this.book.author ?? '',
        genre: this.book.genre ?? '',
        isbn: this.book.isbn ?? '',
        isActive: this.book.is_active ?? true,
      });
    }
  }

  protected get isSubmitting(): boolean {
    return this.state() === 'submitting';
  }

  protected close(): void {
    if (!this.isSubmitting) {
      this.cancelled.emit();
    }
  }

  protected submit(): void {
    this.submitted.set(true);
    if (this.form.invalid || this.isSubmitting) {
      this.toast.set({ type: 'error', text: 'Por favor, corrija os erros no formulário antes de salvar.' });
      return;
    }

    this.state.set('submitting');
    this.toast.set(null);

    const payload = this.buildPayload();
    this.bookService
      .update(this.book.id, payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.state.set('success');
          this.toast.set({ type: 'success', text: 'Obra atualizada com sucesso!' });
          this.saved.emit(updated);
        },
        error: (error: ApiError) => {
          this.state.set('error');
          const message = this.extractErrorMessage(error);
          this.toast.set({ type: 'error', text: message });
        },
      });
  }

  private buildPayload(): BookUpdateRequest {
    const raw = this.form.getRawValue();
    return {
      title: raw.title.trim(),
      author: raw.author.trim(),
      genre: raw.genre.trim() || null,
      isbn: raw.isbn.trim() || null,
      publication_year: raw.publicationYear ? Number(raw.publicationYear) : null,
      publisher: raw.publisher.trim() || null,
      edition: raw.edition.trim() || null,
      cover_url: raw.coverUrl.trim() || null,
      is_active: raw.isActive,
    };
  }

  private extractErrorMessage(error: ApiError): string {
    if (error.status === 404) {
      return 'Obra não encontrada no acervo.';
    }
    if (error.status === 409) {
      return 'O ISBN informado já pertence a outra obra cadastrada.';
    }
    if (error.status === 403) {
      return 'Você não possui permissão para editar obras no acervo.';
    }
    return error.detail || 'Não foi possível atualizar a obra. Tente novamente.';
  }
}
