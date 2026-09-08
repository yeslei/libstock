import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { BookOffer, CatalogBook, LoadState } from '../models/catalog.model';
import { CatalogSearchCriterion, CatalogService } from '../services/catalog.service';

@Component({
  selector: 'app-explore-books',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './explore-books.component.html',
  styleUrl: './explore-books.component.scss',
})
export class ExploreBooksComponent {
  private readonly catalog = inject(CatalogService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly searchCriterion = signal<CatalogSearchCriterion>('title');
  protected readonly searchValue = signal('');
  protected readonly searchState = signal<LoadState<CatalogBook[]> | null>(null);

  protected setSearchCriterion(value: string): void {
    this.searchCriterion.set(value as CatalogSearchCriterion);
  }

  protected setSearchValue(value: string): void {
    this.searchValue.set(value);
  }

  protected search(): void {
    const value = this.searchValue().trim();
    if (!value) {
      this.searchState.set({ status: 'error', message: 'Digite um termo para buscar.' });
      return;
    }

    this.searchState.set({ status: 'loading' });
    this.catalog
      .searchBooks(this.searchCriterion(), value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => this.searchState.set({ status: 'loaded', data }),
        error: () =>
          this.searchState.set({
            status: 'error',
            message: 'Não foi possível realizar a busca. Tente novamente.',
          }),
      });
  }

  protected clearSearch(): void {
    this.searchValue.set('');
    this.searchState.set(null);
  }

  protected offerLabel(offer: BookOffer): string {
    if (!offer.available) {
      return 'Esgotado';
    }
    return offer.destination === 'COMMERCIAL' ? 'Venda' : 'Empréstimo';
  }

  protected offerPrice(offer: BookOffer): string | null {
    if (offer.destination !== 'COMMERCIAL' || offer.price === null) {
      return null;
    }
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(Number(offer.price));
  }
}
