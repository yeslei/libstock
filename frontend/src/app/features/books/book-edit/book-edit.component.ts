import { GenrePickerComponent } from '../components/genre-picker/genre-picker.component';
import { Genre } from '../../catalog/models/catalog.model';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { BookDetail } from '../models/book.model';
import { BookService } from '../services/book.service';
import { isbnValidator } from '../validators/isbn.validator';

type EditState = 'loading' | 'ready' | 'submitting' | 'success' | 'error';

@Component({
  selector: 'app-book-edit',
  standalone: true,
  imports: [
    GenrePickerComponent,
    ReactiveFormsModule,
    RouterLink,
    AlertComponent,
    SpinnerComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './book-edit.component.html',
  styleUrl: './book-edit.component.scss',
})
export class BookEditComponent {
  private readonly fb = inject(FormBuilder);
  private readonly books = inject(BookService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly bookId = Number(this.route.snapshot.paramMap.get('id'));

  protected readonly state = signal<EditState>('loading');
  protected readonly message = signal<string | null>(null);
  protected readonly book = signal<BookDetail | null>(null);
  protected readonly selectedGenres = signal<readonly Genre[]>([]);
  protected genreIds(): readonly number[] {
    return this.selectedGenres().map((genre) => genre.id);
  }
  protected readonly imageFailed = signal(false);
  protected readonly form = this.fb.nonNullable.group({
    isbn: ['', [isbnValidator]],
    title: ['', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(255)]],
    author: ['', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(255)]],
    genre: ['', [Validators.maxLength(100)]],
    publisher: ['', Validators.maxLength(150)],
    edition: ['', Validators.maxLength(50)],
    publicationYear: [
      '',
      [Validators.min(1000), Validators.max(2100), Validators.pattern(/^\d{4}$/)],
    ],
    coverUrl: ['', [Validators.pattern(/^https?:\/\/.+/i)]],
  });

  constructor() {
    if (!Number.isSafeInteger(this.bookId) || this.bookId <= 0) {
      this.state.set('error');
      this.message.set('O identificador da obra é inválido.');
      return;
    }
    this.books
      .get(this.bookId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (book) => {
          this.book.set(book);
          this.selectedGenres.set(book.genres ?? []);
          this.form.setValue({
            isbn: book.isbn ?? '',
            title: book.title,
            author: book.author,
            genre: book.genre ?? '',
            coverUrl: book.cover_url ?? '',
            publisher: book.publisher ?? '',
            edition: book.edition ?? '',
            publicationYear: String(book.publication_year ?? ''),
          });
          this.state.set('ready');
        },
        error: (error: ApiError) => {
          this.state.set('error');
          this.message.set(error.detail);
        },
      });
  }

  protected save(): void {
    if (this.form.invalid || this.state() === 'submitting') {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.state.set('submitting');
    this.message.set(null);
    this.books
      .update(this.bookId, {
        isbn: value.isbn.trim() || null,
        title: value.title.trim(),
        author: value.author.trim(),
        publisher: value.publisher.trim() || null,
        edition: value.edition.trim() || null,
        publication_year: value.publicationYear ? Number(value.publicationYear) : null,
        genre_ids: this.genreIds(),
        cover_url: value.coverUrl.trim() || null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (book) => {
          this.book.set(book);
          this.imageFailed.set(false);
          this.state.set('success');
          this.message.set('Obra atualizada com sucesso.');
        },
        error: (error: ApiError) => {
          this.state.set('error');
          this.message.set(
            error.status === 403 ? 'Você não tem permissão para alterar esta obra.' : error.detail,
          );
        },
      });
  }
}
