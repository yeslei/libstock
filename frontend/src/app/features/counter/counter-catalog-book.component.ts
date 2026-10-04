import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, map, merge, switchMap } from 'rxjs';

import { ApiError } from '../../core/models/auth.model';
import { LoadState } from '../../core/models/load-state.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { BookService } from '../books/services/book.service';
import { CopyService } from '../copies/services/copy.service';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { CounterService, StaffCatalogBookDetail, StaffCatalogCopy } from './counter.service';
import { ActionFlow, copyStatusLabel, destinationLabel, toLoadState } from './desk-flow';

/** Papéis que o backend autoriza em `PATCH /api/v1/books/{id}`. No balcão, apenas ADMINISTRATOR chega à tela. */
const EDIT_ROLES = ['STOCK_KEEPER', 'MANAGER', 'ADMINISTRATOR'];
/** Papéis que o backend autoriza em `POST /api/v1/copies/`. */
const COPY_ROLES = ['STOCK_KEEPER', 'ADMINISTRATOR'];
/** Papéis que o backend autoriza em `DELETE /api/v1/copies/{id}`. No balcão, apenas ADMINISTRATOR chega à tela. */
const DELETE_COPY_ROLES = ['STOCK_KEEPER', 'ADMINISTRATOR'];
const GENRE_MAX = 100;

/** Estado "bloqueada" (frames 04_2 e 05_2): motivos e vínculos devolvidos pelo 409 do backend. */
interface BlockedState {
  readonly kind: 'book' | 'copy';
  readonly title: string;
  readonly headline: string;
  readonly note: string;
  readonly sectionTitle: string;
  readonly lines: readonly string[];
}

interface OperationLink {
  readonly type: 'open_loan' | 'pending_loan_request' | 'purchase_reservation';
  readonly copy_barcode: string | null;
  readonly client_name?: string | null;
}

interface BlockDetails {
  readonly reasons?: readonly { readonly message?: string }[];
  readonly history?: Readonly<Record<string, number>>;
  readonly counts?: Readonly<Record<string, number>>;
  readonly links?: readonly OperationLink[];
}

const HISTORY_LABEL: Readonly<Record<string, string>> = {
  loans: 'Empréstimos',
  sales: 'Vendas',
  purchase_reservations: 'Reservas de compra',
  requests: 'Solicitações vinculadas',
};

const COUNT_LABEL: Readonly<Record<string, string>> = {
  open_loans: 'Empréstimos em aberto',
  pending_loan_requests: 'Solicitações de retirada pendentes',
  purchase_reservations: 'Reservas de compra aguardando ou com exemplar destinado',
};

const LINK_LABEL: Readonly<Record<OperationLink['type'], string>> = {
  open_loan: 'empréstimo ativo',
  pending_loan_request: 'solicitação de retirada pendente',
  purchase_reservation: 'reserva de compra',
};

function describeLink(link: OperationLink): string {
  return [link.copy_barcode ? `Exemplar #${link.copy_barcode}` : null, LINK_LABEL[link.type], link.client_name]
    .filter((part): part is string => !!part)
    .join(' · ');
}

function positiveEntries(values: Readonly<Record<string, number>> | undefined, labels: Readonly<Record<string, string>>): string[] {
  return Object.entries(values ?? {})
    .filter(([key, count]) => count > 0 && key in labels)
    .map(([key, count]) => `${labels[key]}: ${count}`);
}

/**
 * Frames "Funcionário / Acervo / Detalhes da obra" e "Exemplares": dados da obra e exemplares em leitura.
 * Categoria e inativação usam o endpoint existente de obras e só aparecem para os papéis autorizados.
 * Inclusão de exemplar tem tela própria (/exemplares/novo). Exclusão de exemplar (só disponível e sem histórico) e inativação (bloqueada por operações em andamento) seguem a decisão delegada de 2026-10-03 (BUSINESS_RULES); o backend decide e a tela mostra os motivos do 409. Edição/conversão de exemplar e reativação não têm endpoint nem regra aprovada.
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
  private readonly copies = inject(CopyService);
  private readonly reloads = new Subject<void>();
  private readonly route = inject(ActivatedRoute);
  private currentId = 0;

  protected readonly state = signal<LoadState<StaffCatalogBookDetail>>({ status: 'loading' });
  protected readonly canEdit = (inject(TokenStoreService).user?.role_codes ?? []).some((role) => EDIT_ROLES.includes(role));
  protected readonly canAddCopy = (inject(TokenStoreService).user?.role_codes ?? []).some((role) => COPY_ROLES.includes(role));
  protected readonly canDeleteCopy = (inject(TokenStoreService).user?.role_codes ?? []).some((role) => DELETE_COPY_ROLES.includes(role));
  protected readonly blocked = signal<BlockedState | null>(null);
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
    this.blocked.set(null);
    const next = this.genre().trim() || null;
    this.flow.ask({
      title: 'Salvar alteração da obra?',
      details: [`Obra: ${book.title}`, `Categoria: ${book.genre ?? 'sem categoria'} → ${next ?? 'sem categoria'}`],
      confirmLabel: 'Salvar alteração',
      run: () => this.books.update(book.id, { genre: next }),
      success: () => `Categoria de “${book.title}” atualizada.`,
    });
  }

  /** Situação lida dos exemplares carregados; a decisão final é do backend, que também confere solicitações e reservas. */
  protected deactivationSituation(book: StaffCatalogBookDetail): string[] {
    const active = book.copies.filter((copy) => copy.is_active);
    const borrowed = active.filter((copy) => copy.status === 'BORROWED');
    const reserved = active.filter((copy) => copy.allocated_for_purchase);
    const lines = [book.total_copies === 1 ? '1 exemplar vinculado' : `${book.total_copies} exemplares vinculados`];
    if (!borrowed.length && !reserved.length) {
      lines.push('Nenhum exemplar emprestado ou reservado para venda');
      return lines;
    }
    for (const copy of borrowed) lines.push(`Exemplar ${copy.barcode} emprestado (bloqueia a inativação)`);
    for (const copy of reserved) lines.push(`Exemplar ${copy.barcode} reservado para venda (bloqueia a inativação)`);
    return lines;
  }

  protected askDeactivate(book: StaffCatalogBookDetail): void {
    if (!this.canEdit || !book.is_active) return;
    this.blocked.set(null);
    this.flow.ask({
      title: `Inativar ${book.title}?`,
      intro: 'A obra deixa de aparecer no acervo ativo e não aceita novos exemplares. Os registros anteriores são preservados. Não há reativação por esta tela. A inativação é bloqueada enquanto houver empréstimo em aberto, solicitação de retirada pendente ou reserva de compra aguardando ou com exemplar destinado.',
      detailsTitle: 'Situação verificada',
      details: this.deactivationSituation(book),
      confirmLabel: 'Confirmar inativação',
      run: () => this.books.update(book.id, { is_active: false }),
      success: () => `${book.title} foi inativada. O histórico foi preservado.`,
      onError: (error) => this.showBookBlock(error),
    });
  }

  /** Motivo exibido junto ao botão desabilitado e em title, para antecipar o botão desabilitado; null quando o backend deve decidir. */
  protected deleteCopyBlockReason(book: StaffCatalogBookDetail, copy: StaffCatalogCopy): string | null {
    if (copy.status !== 'AVAILABLE') return `Exemplar ${copyStatusLabel(copy).toLowerCase()}: só exemplares disponíveis podem ser excluídos.`;
    if (copy.allocated_for_purchase) return 'Exemplar reservado para venda: não pode ser excluído.';
    if (book.is_active && copy.is_active && !book.copies.some((other) => other.id !== copy.id && other.is_active)) {
      return 'Último exemplar ativo da obra: não pode ser excluído.';
    }
    return null;
  }

  protected askDeleteCopy(book: StaffCatalogBookDetail, copy: StaffCatalogCopy): void {
    if (!this.canDeleteCopy || this.deleteCopyBlockReason(book, copy)) return;
    this.blocked.set(null);
    const before = book.total_copies;
    const after = copy.is_active && copy.status !== 'SOLD' ? before - 1 : before;
    this.flow.ask({
      title: `Excluir exemplar #${copy.barcode}?`,
      intro: `Você está excluindo somente esta cópia de ${book.title}. A obra e os outros exemplares serão mantidos.`,
      detailsTitle: 'Confira o exemplar',
      details: [
        `#${copy.barcode} · ${destinationLabel(copy.destination)} · ${copyStatusLabel(copy)}`,
        `Quantidade da obra após exclusão: ${before} → ${after}`,
        'Esta ação remove a cópia do acervo.',
      ],
      confirmLabel: 'Excluir exemplar',
      run: () => this.copies.delete(copy.id),
      success: (result) =>
        `Exemplar #${result.barcode} excluído. A quantidade de ${book.title} foi atualizada de ${before} para ${after} ${after === 1 ? 'exemplar' : 'exemplares'}.`,
      onError: (error) => this.showCopyBlock(error),
    });
  }

  protected dismissBlocked(): void {
    this.blocked.set(null);
  }

  private showCopyBlock(error: unknown): boolean {
    const failure = error as Partial<ApiError> | null;
    if (failure?.status !== 409) return false;
    const details = (failure.details ?? {}) as BlockDetails;
    const reasons = (details.reasons ?? []).map((reason) => reason.message).filter((message): message is string => !!message);
    this.blocked.set({
      kind: 'copy',
      title: 'Exclusão bloqueada',
      headline: failure.detail ?? 'Este exemplar não pode ser excluído.',
      note: 'A exclusão não pode ser concluída enquanto houver operação ativa ou histórico.',
      sectionTitle: 'Motivos do bloqueio',
      lines: [...reasons, ...positiveEntries(details.history, HISTORY_LABEL)],
    });
    return true;
  }

  private showBookBlock(error: unknown): boolean {
    const failure = error as Partial<ApiError> | null;
    if (failure?.status !== 409 || failure.code !== 'book_has_active_operations') return false;
    const details = (failure.details ?? {}) as BlockDetails;
    this.blocked.set({
      kind: 'book',
      title: 'Inativação bloqueada',
      headline: 'Esta obra possui operações ativas',
      note: 'Regularize os vínculos antes de tentar inativar.',
      sectionTitle: 'Vínculos encontrados',
      lines: [...positiveEntries(details.counts, COUNT_LABEL), ...(details.links ?? []).map(describeLink)],
    });
    return true;
  }
}
