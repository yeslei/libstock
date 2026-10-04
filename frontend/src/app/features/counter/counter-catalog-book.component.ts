import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, map, merge, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { BookService } from '../books/services/book.service';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { CounterService, StaffCatalogBookDetail } from './counter.service';
import { ActionFlow, copyStatusLabel, destinationLabel, toLoadState } from './desk-flow';

/** Papéis que o backend autoriza em `PATCH /api/v1/books/{id}`. No balcão, apenas ADMINISTRATOR chega à tela. */
const EDIT_ROLES = ['STOCK_KEEPER', 'MANAGER', 'ADMINISTRATOR'];
const GENRE_MAX = 100;

/**
 * Frames "Funcionário / Acervo / Detalhes da obra" e "Exemplares": dados da obra e exemplares em leitura.
 * Categoria e inativação usam o endpoint existente de obras e só aparecem para os papéis autorizados.
 * Edição/conversão/exclusão de exemplar e reativação não têm endpoint nem regra aprovada (BUSINESS_RULES, seção 21).
 */
@Component({
  selector: 'app-counter-catalog-book',
  standalone: true,
  imports: [RouterLink, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-catalog-book.component.html',
  styleUrl: './counter-catalog.component.scss',
})
export class CounterCatalogBookComponent {
  private readonly counter = inject(CounterService);
  private readonly books = inject(BookService);
  private readonly reloads = new Subject<void>();
  private readonly route = inject(ActivatedRoute);
  private currentId = 0;

  protected readonly state = signal<LoadState<StaffCatalogBookDetail>>({ status: 'loading' });
  protected readonly canEdit = (inject(TokenStoreService).user?.role_codes ?? []).some((role) => EDIT_ROLES.includes(role));
  protected readonly editing = signal(false);
  protected readonly genre = signal('');
  protected readonly genreMax = GENRE_MAX;
  protected readonly flow = new ActionFlow(inject(DestroyRef), () => this.reload());
  protected readonly destinationLabel = destinationLabel;
  protected readonly copyStatusLabel = copyStatusLabel;
  protected readonly genreTooLong = computed(() => this.genre().trim().length > GENRE_MAX);

  constructor() {
    merge(
      this.route.paramMap.pipe(map((params) => (this.currentId = Number(params.get('id'))))),
      this.reloads.pipe(map(() => this.currentId)),
    )
      .pipe(
        switchMap((id) => toLoadState(this.counter.getCatalogBook(id), 'Não foi possível carregar a obra.')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((state) => {
        this.state.set(state);
        if (state.status === 'loaded') this.genre.set(state.data.genre ?? '');
      });
  }

  protected reload(): void {
    this.reloads.next();
  }

  protected setGenre(event: Event): void {
    this.genre.set((event.target as HTMLInputElement).value);
  }

  protected startEditing(): void {
    this.editing.set(true);
  }

  protected changed(book: StaffCatalogBookDetail): boolean {
    return this.genre().trim() !== (book.genre ?? '');
  }

  protected askSaveGenre(book: StaffCatalogBookDetail): void {
    if (!this.canEdit || this.genreTooLong() || !this.changed(book)) return;
    const next = this.genre().trim() || null;
    this.flow.ask({
      title: 'Salvar alteração da obra?',
      details: [`Obra: ${book.title}`, `Categoria: ${book.genre ?? 'sem categoria'} → ${next ?? 'sem categoria'}`],
      confirmLabel: 'Salvar alteração',
      run: () => this.books.update(book.id, { genre: next }),
      success: () => `Categoria de “${book.title}” atualizada.`,
    });
  }

  protected askDeactivate(book: StaffCatalogBookDetail): void {
    if (!this.canEdit || !book.is_active) return;
    this.flow.ask({
      title: 'Inativar obra?',
      details: [
        `Obra: ${book.title}`,
        'A obra deixa de aparecer no acervo ativo. Não há reativação por esta tela.',
      ],
      confirmLabel: 'Inativar obra',
      run: () => this.books.update(book.id, { is_active: false }),
      success: () => `Obra “${book.title}” inativada.`,
    });
  }
}

