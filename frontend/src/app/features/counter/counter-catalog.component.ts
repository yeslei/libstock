import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, switchMap } from 'rxjs';

import { LoadState } from '../../core/models/load-state.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { CounterService, LIST_LIMIT, StaffCatalogBook } from './counter.service';
import { toLoadState } from './desk-flow';

/** Papéis que o backend autoriza em `POST /api/v1/books/` (Issue #151: o vendedor administra o acervo). */
const CREATE_BOOK_ROLES = ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'];

/** Frame "Funcionário / Acervo" (painel 03): obras cadastradas, busca e acesso à obra. Consulta somente leitura. */
@Component({
  selector: 'app-counter-catalog',
  standalone: true,
  imports: [RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-catalog.component.html',
  styleUrl: './counter-catalog.component.scss',
})
export class CounterCatalogComponent implements OnInit {
  private readonly service = inject(CounterService);
  private readonly loads = new Subject<void>();

  protected readonly term = signal('');
  protected readonly state = signal<LoadState<readonly StaffCatalogBook[]>>({ status: 'loading' });
  protected readonly limit = LIST_LIMIT;
  /** Cadastro de obra só para quem o backend autoriza (SELLER, STOCK_KEEPER, ADMINISTRATOR). */
  protected readonly canCreate = (inject(TokenStoreService).user?.role_codes ?? []).some((role) => CREATE_BOOK_ROLES.includes(role));

  constructor() {
    this.loads
      .pipe(
        switchMap(() => toLoadState(this.service.listCatalogBooks(this.term()), 'Não foi possível carregar o acervo.')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((state) => this.state.set(state));
  }

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loads.next();
  }

  protected setTerm(event: Event): void {
    this.term.set((event.target as HTMLInputElement).value);
  }

  protected search(event: Event): void {
    event.preventDefault();
    this.reload();
  }

  protected copiesLabel(book: StaffCatalogBook): string {
    return book.total_copies === 1 ? '1 cópia' : `${book.total_copies} cópias`;
  }
}
