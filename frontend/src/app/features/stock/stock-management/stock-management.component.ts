import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { BookDetail } from '../../books/models/book.model';
import { BookService } from '../../books/services/book.service';
import { CatalogBook, LoadState } from '../../catalog/models/catalog.model';
import { CatalogSearchCriterion, CatalogService } from '../../catalog/services/catalog.service';

@Component({
  selector: 'app-stock-management',
  standalone: true,
  imports: [RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './stock-management.component.html',
  styleUrl: './stock-management.component.scss',
})
export class StockManagementComponent {
  private readonly catalog = inject(CatalogService);
  private readonly books = inject(BookService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly criterion = signal<CatalogSearchCriterion>('title');
  protected readonly term = signal('');
  protected readonly results = signal<LoadState<CatalogBook[]> | null>(null);
  protected readonly selected = signal<LoadState<BookDetail> | null>(null);

  protected search(): void {
    const term = this.term().trim();
    if (!term) {
      this.results.set({ status: 'error', message: 'Digite um termo para pesquisar.' });
      return;
    }
    this.results.set({ status: 'loading' });
    this.selected.set(null);
    this.catalog.searchBooks(this.criterion(), term).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => this.results.set({ status: 'loaded', data }),
      error: (error: ApiError) => this.results.set({ status: 'error', message: error.detail }),
    });
  }

  protected select(bookId: number): void {
    this.selected.set({ status: 'loading' });
    this.books.get(bookId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => this.selected.set({ status: 'loaded', data }),
      error: (error: ApiError) => this.selected.set({ status: 'error', message: error.detail }),
    });
  }
}
