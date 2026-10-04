import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { SpinnerComponent } from '../../../../shared/components/spinner/spinner.component';
import { Genre } from '../../../catalog/models/catalog.model';
import { CatalogService } from '../../../catalog/services/catalog.service';

type PickerState =
  | { readonly status: 'loading' }
  | { readonly status: 'error' }
  | { readonly status: 'loaded'; readonly genres: readonly Genre[] };

/**
 * Seleção múltipla das categorias do catálogo (`GET /api/v1/catalog/genres?all=true`), usada no
 * cadastro e na edição de obra (Issue #174). O valor é a lista de ids para `genre_ids`.
 */
@Component({
  selector: 'app-genre-picker',
  standalone: true,
  imports: [SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './genre-picker.component.html',
  styleUrl: './genre-picker.component.scss',
})
export class GenrePickerComponent {
  private readonly catalog = inject(CatalogService);
  private readonly destroyRef = inject(DestroyRef);

  readonly selected = input<readonly number[]>([]);
  readonly disabled = input(false);
  readonly idPrefix = input('genre');
  /** Categorias escolhidas (objetos do catálogo, na ordem de seleção); os ids vão em `genre_ids`. */
  readonly selectedChange = output<Genre[]>();

  protected readonly state = signal<PickerState>({ status: 'loading' });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.state.set({ status: 'loading' });
    this.catalog
      .getAllGenres()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (genres) => this.state.set({ status: 'loaded', genres }),
        error: () => this.state.set({ status: 'error' }),
      });
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected toggle(genre: Genre): void {
    const state = this.state();
    if (state.status !== 'loaded') return;
    const known = new Map(state.genres.map((item) => [item.id, item]));
    const ids = this.selected().includes(genre.id)
      ? this.selected().filter((id) => id !== genre.id)
      : [...this.selected(), genre.id];
    // Ids selecionados que o catálogo não lista mais são descartados: o backend os recusaria (404).
    this.selectedChange.emit(ids.flatMap((id) => known.get(id) ?? []));
  }
}
