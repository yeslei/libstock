import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, map, merge, switchMap } from 'rxjs';

import { ApiError } from '../../core/models/auth.model';
import { LoadState } from '../../core/models/load-state.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { GenrePickerComponent } from '../books/components/genre-picker/genre-picker.component';
import { BookService } from '../books/services/book.service';
import { CopyService } from '../copies/services/copy.service';
import { SaveFailureComponent } from './save-failure.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import {
  CopyDestination,
  CounterService,
  StaffCatalogBookDetail,
  StaffCatalogCopy,
  StaffGenre,
} from './counter.service';
import {
  ActionFlow,
  copyStatusLabel,
  destinationLabel,
  formatPrice,
  genreLabel,
  toLoadState,
} from './desk-flow';

/**
 * Issue #169: o estoquista usa o balcão restrito ao cadastro (consulta, nova obra e novo exemplar). Edição e inativação/reativação de obra
 * e edição, conversão e exclusão de exemplar ficam ocultas para ele, embora o backend mantenha as permissões de escrita da matriz da #151.
 */
const MANAGE_BOOK_ROLES = ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'];
const MANAGE_COPY_ROLES = ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'];
/** Papéis que o backend autoriza em `POST /api/v1/copies` e que a tela oferece (inclui o estoquista). */
const ADD_COPY_ROLES = ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'];
const CONDITION_MAX = 30;
const PRICE_PATTERN = /^\d+(?:\.\d{1,2})?$/;

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
  return [
    link.copy_barcode ? `Exemplar #${link.copy_barcode}` : null,
    LINK_LABEL[link.type],
    link.client_name,
  ]
    .filter((part): part is string => !!part)
    .join(' · ');
}

function positiveEntries(
  values: Readonly<Record<string, number>> | undefined,
  labels: Readonly<Record<string, string>>,
): string[] {
  return Object.entries(values ?? {})
    .filter(([key, count]) => count > 0 && key in labels)
    .map(([key, count]) => `${labels[key]}: ${count}`);
}

/**
 * Frames "Funcionário / Acervo / Detalhes da obra" e "Exemplares": dados da obra e exemplares em leitura.
 * Categoria e inativação usam o endpoint existente de obras e só aparecem para os papéis autorizados.
 * Inclusão de exemplar tem tela própria (/exemplares/novo). Exclusão de exemplar (só disponível e sem histórico), inativação (bloqueada por operações em andamento), reativação (exige exemplar ativo) e edição/conversão de exemplar (só disponível, ativo e sem operação) seguem as decisões delegadas de 2026-10-03 (BUSINESS_RULES, Issues #135, #147 e #151); o backend decide e a tela mostra os motivos do 409.
 */
@Component({
  selector: 'app-counter-catalog-book',
  standalone: true,
  imports: [
    SaveFailureComponent,
    RouterLink,
    AlertComponent,
    SpinnerComponent,
    ConfirmDialogComponent,
    GenrePickerComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-catalog-book.component.html',
  styleUrl: './counter-catalog-book.component.scss',
})
export class CounterCatalogBookComponent {
  private readonly counter = inject(CounterService);
  private readonly books = inject(BookService);
  private readonly copies = inject(CopyService);
  private readonly reloads = new Subject<void>();
  private readonly route = inject(ActivatedRoute);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private currentId = 0;

  protected readonly state = signal<LoadState<StaffCatalogBookDetail>>({ status: 'loading' });
  private readonly roleCodes = inject(TokenStoreService).user?.role_codes ?? [];
  protected readonly canEdit = this.roleCodes.some((role) => MANAGE_BOOK_ROLES.includes(role));
  protected readonly canAddCopy = this.roleCodes.some((role) => ADD_COPY_ROLES.includes(role));
  protected readonly canDeleteCopy = this.roleCodes.some((role) =>
    MANAGE_COPY_ROLES.includes(role),
  );
  protected readonly canEditCopy = this.canDeleteCopy;
  protected readonly selectedCopyId = signal<number | null>(null);
  protected readonly editingCopyId = signal<number | null>(null);
  protected readonly copyDestination = signal<CopyDestination>('DIDACTIC');
  protected readonly copyPrice = signal('');
  protected readonly copyCondition = signal('');
  protected readonly conditionMax = CONDITION_MAX;
  protected readonly blocked = signal<BlockedState | null>(null);
  protected readonly editing = signal(false);
  /** Categorias do catálogo escolhidas na edição (Issue #174); começam nas atuais da obra. */
  protected readonly selectedGenres = signal<readonly StaffGenre[]>([]);
  protected readonly genreIds = computed(() => this.selectedGenres().map((genre) => genre.id));
  protected readonly genreLabel = genreLabel;
  protected readonly flow = new ActionFlow(inject(DestroyRef), (succeeded) => {
    if (succeeded) {
      this.editingCopyId.set(null);
      this.selectedCopyId.set(null);
    }
    this.reload();
  });
  protected readonly formatPrice = formatPrice;
  protected readonly destinationLabel = destinationLabel;
  protected readonly copyStatusLabel = copyStatusLabel;
  protected readonly conditionTooLong = computed(
    () => this.copyCondition().trim().length > CONDITION_MAX,
  );
  protected readonly priceError = computed(() => {
    if (this.copyDestination() !== 'COMMERCIAL') return null;
    const value = this.normalizedPrice();
    if (!value) return 'Informe o preço de venda para converter ou manter o exemplar como Venda.';
    if (!PRICE_PATTERN.test(value) || value.replace('.', '').length > 10) {
      return 'Informe um preço com até 10 dígitos e duas casas decimais.';
    }
    return Number(value) > 0 ? null : 'O preço de venda deve ser maior que zero.';
  });

  constructor() {
    merge(
      this.route.paramMap.pipe(map((params) => (this.currentId = Number(params.get('id'))))),
      this.reloads.pipe(map(() => this.currentId)),
    )
      .pipe(
        switchMap((id) =>
          toLoadState(this.counter.getCatalogBook(id), 'Não foi possível carregar a obra.'),
        ),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((state) => {
        this.state.set(state);
        if (state.status === 'loaded') this.selectedGenres.set(state.data.genres);
      });
  }

  protected selectedCopy(book: StaffCatalogBookDetail): StaffCatalogCopy | null {
    return book.copies.find((copy) => copy.id === this.selectedCopyId()) ?? null;
  }

  protected selectCopy(copy: StaffCatalogCopy): void {
    if (!this.canEditCopy || this.flow.submitting()) return;
    this.editingCopyId.set(null);
    this.selectedCopyId.set(copy.id);
    setTimeout(() => {
      const heading = this.host.nativeElement.querySelector<HTMLElement>('#selected-copy-title');
      heading?.scrollIntoView({ block: 'nearest' });
      heading?.focus({ preventScroll: true });
    });
  }

  protected closeCopy(): void {
    if (!this.flow.submitting()) {
      this.selectedCopyId.set(null);
      this.editingCopyId.set(null);
    }
  }

  protected readonly copyFilter = signal<'all' | 'DIDACTIC' | 'COMMERCIAL' | 'inactive'>('all');
  protected readonly copyPage = signal(0);
  protected copyPageCount(book: StaffCatalogBookDetail): number {
    return Math.max(1, Math.ceil(this.filteredCopies(book).length / 5));
  }
  protected currentCopyPage(book: StaffCatalogBookDetail): number {
    return Math.min(this.copyPage(), this.copyPageCount(book) - 1);
  }
  protected pagedCopies(book: StaffCatalogBookDetail): readonly StaffCatalogCopy[] {
    const start = this.currentCopyPage(book) * 5;
    return this.filteredCopies(book).slice(start, start + 5);
  }
  protected filteredCopies(book: StaffCatalogBookDetail): readonly StaffCatalogCopy[] {
    const filter = this.copyFilter();
    return book.copies.filter(
      (copy) =>
        filter === 'all' ||
        (filter === 'inactive' ? !copy.is_active : copy.is_active && copy.destination === filter),
    );
  }
  protected availableCopies(
    book: StaffCatalogBookDetail,
    destination: 'DIDACTIC' | 'COMMERCIAL',
  ): number {
    return book.is_active
      ? book.copies.filter((copy) => copy.free && copy.destination === destination).length
      : 0;
  }
  protected inactiveCopies(book: StaffCatalogBookDetail): number {
    return book.copies.filter((copy) => !copy.is_active).length;
  }
  protected borrowedCopies(book: StaffCatalogBookDetail): number {
    return book.copies.filter((copy) => copy.status === 'BORROWED').length;
  }
  protected activityReason(book: StaffCatalogBookDetail, copy: StaffCatalogCopy): string | null {
    if (copy.is_active && !copy.free)
      return 'Conclua o empréstimo, a reserva ou a venda antes de inativar.';
    if (!copy.is_active && !['AVAILABLE', 'INACTIVE'].includes(copy.status))
      return 'Este exemplar tem uma operação pendente.';
    if (
      copy.is_active &&
      book.is_active &&
      !book.copies.some((other) => other.id !== copy.id && other.is_active)
    )
      return 'Último exemplar ativo: inative a obra para retirar todo o acervo de circulação.';
    return null;
  }
  protected askActivity(book: StaffCatalogBookDetail, copy: StaffCatalogCopy): void {
    if (!this.canEditCopy || this.activityReason(book, copy)) return;
    const active = !copy.is_active;
    this.flow.ask({
      title: `${active ? 'Reativar' : 'Inativar'} exemplar ${copy.barcode}?`,
      intro: active
        ? 'O exemplar voltará a participar da disponibilidade da obra.'
        : 'O exemplar sairá da disponibilidade. Seu cadastro e histórico serão preservados.',
      details: [book.title, copy.barcode, destinationLabel(copy.destination)],
      confirmLabel: active ? 'Reativar exemplar' : 'Inativar exemplar',
      run: () => this.copies.update(copy.id, { isActive: active }),
      success: () => `Exemplar ${active ? 'reativado' : 'inativado'} com sucesso.`,
    });
  }

  protected reload(): void {
    this.reloads.next();
  }

  protected startEditing(): void {
    this.editing.set(true);
  }

  protected cancelEditing(): void {
    if (this.flow.submitting()) return;
    const state = this.state();
    if (state.status === 'loaded') this.selectedGenres.set(state.data.genres);
    this.editing.set(false);
  }

  protected changed(book: StaffCatalogBookDetail): boolean {
    const current = new Set(book.genres.map((genre) => genre.id));
    const next = new Set(this.genreIds());
    return current.size !== next.size || [...next].some((id) => !current.has(id));
  }

  protected askSaveGenre(book: StaffCatalogBookDetail): void {
    if (!this.canEdit || !this.changed(book)) return;
    this.blocked.set(null);
    const ids = this.genreIds();
    const next =
      this.selectedGenres()
        .map((genre) => genre.name)
        .join(', ') || null;
    this.flow.ask({
      title: 'Salvar alteração da obra?',
      details: [
        `Obra: ${book.title}`,
        `Categorias: ${genreLabel(book) ?? 'sem categoria'} → ${next ?? 'sem categoria'}`,
      ],
      confirmLabel: 'Salvar alteração',
      run: () => this.books.update(book.id, { genre_ids: ids }),
      success: () => `Categorias de “${book.title}” atualizadas.`,
    });
  }

  /** Exemplar em edição, lido da obra recarregada: some se deixou de ser editável. */
  protected editingCopy(book: StaffCatalogBookDetail): StaffCatalogCopy | null {
    const id = this.editingCopyId();
    const copy = id === null ? null : (book.copies.find((item) => item.id === id) ?? null);
    return copy && !this.editCopyBlockReason(copy) ? copy : null;
  }

  /** Motivo que antecipa o botão "Editar" desabilitado; null quando o backend deve decidir. */
  protected editCopyBlockReason(copy: StaffCatalogCopy): string | null {
    if (!copy.is_active || copy.status === 'INACTIVE')
      return 'Exemplar inativo: não pode ser editado.';
    if (copy.allocated_for_purchase) return 'Exemplar reservado para venda: não pode ser editado.';
    if (!copy.free)
      return `Exemplar ${copyStatusLabel(copy).toLowerCase()}: só exemplares disponíveis podem ser editados.`;
    return null;
  }

  protected startEditingCopy(copy: StaffCatalogCopy): void {
    if (!this.canEditCopy || this.editCopyBlockReason(copy)) return;
    this.blocked.set(null);
    this.copyDestination.set(copy.destination);
    this.copyPrice.set(
      copy.sale_price === null || copy.sale_price === ''
        ? ''
        : String(copy.sale_price).replace('.', ','),
    );
    this.copyCondition.set(copy.condition ?? '');
    this.editingCopyId.set(copy.id);
    setTimeout(() => {
      const heading = this.host.nativeElement.querySelector<HTMLElement>('#editar-exemplar-titulo');
      heading?.scrollIntoView({ block: 'center' });
      heading?.focus({ preventScroll: true });
    });
  }

  protected cancelEditingCopy(): void {
    if (!this.flow.submitting()) this.editingCopyId.set(null);
  }

  protected setCopyDestination(event: Event): void {
    this.copyDestination.set((event.target as HTMLSelectElement).value as CopyDestination);
  }

  protected setCopyPrice(event: Event): void {
    this.copyPrice.set((event.target as HTMLInputElement).value);
  }

  protected setCopyCondition(event: Event): void {
    this.copyCondition.set((event.target as HTMLInputElement).value);
  }

  /** Só o que mudou vai ao backend; para Empréstimo o preço é removido pelo backend e nunca enviado. */
  private copyChanges(copy: StaffCatalogCopy): {
    destination?: CopyDestination;
    salePrice?: number;
    condition?: string | null;
  } {
    const changes: {
      destination?: CopyDestination;
      salePrice?: number;
      condition?: string | null;
    } = {};
    const destination = this.copyDestination();
    if (destination !== copy.destination) changes.destination = destination;
    if (destination === 'COMMERCIAL') {
      const price = Number(this.normalizedPrice());
      if (destination !== copy.destination || price !== Number(copy.sale_price))
        changes.salePrice = price;
    }
    const condition = this.copyCondition().trim() || null;
    if (condition !== (copy.condition ?? null)) changes.condition = condition;
    return changes;
  }

  protected copyChanged(copy: StaffCatalogCopy): boolean {
    return Object.keys(this.copyChanges(copy)).length > 0;
  }

  protected conversionNote(copy: StaffCatalogCopy): string {
    return copy.destination === 'COMMERCIAL'
      ? 'Exemplar destinado à venda. Converter para Empréstimo remove o preço de venda.'
      : 'Exemplar destinado a empréstimo. Converter para Venda exige preço de venda.';
  }

  protected askSaveCopy(book: StaffCatalogBookDetail, copy: StaffCatalogCopy): void {
    if (
      !this.canEditCopy ||
      this.editCopyBlockReason(copy) ||
      this.priceError() ||
      this.conditionTooLong() ||
      !this.copyChanged(copy)
    )
      return;
    const changes = this.copyChanges(copy);
    const after = changes.destination ?? copy.destination;
    const details = [`Exemplar #${copy.barcode} · ${book.title}`];
    if (changes.destination)
      details.push(
        `Finalidade: ${destinationLabel(copy.destination)} → ${destinationLabel(after)}`,
      );
    if (after === 'COMMERCIAL' && changes.salePrice !== undefined) {
      details.push(
        `Preço de venda: ${formatPrice(copy.sale_price)} → ${formatPrice(changes.salePrice)}`,
      );
    } else if (changes.destination === 'DIDACTIC') {
      details.push(`Preço de venda: ${formatPrice(copy.sale_price)} → removido`);
    }
    if (changes.condition !== undefined)
      details.push(
        `Condição: ${copy.condition ?? 'não informada'} → ${changes.condition ?? 'não informada'}`,
      );
    this.blocked.set(null);
    this.flow.ask({
      title: `Salvar alterações do exemplar #${copy.barcode}?`,
      intro:
        'O código do exemplar não muda. A edição só é aceita para exemplar disponível, sem reserva destinada nem operação em andamento.',
      detailsTitle: 'Confira as alterações',
      details,
      confirmLabel: 'Salvar exemplar',
      run: () => this.copies.update(copy.id, changes),
      success: () => `Exemplar #${copy.barcode} atualizado.`,
    });
  }

  private normalizedPrice(): string {
    return this.copyPrice().trim().replace(',', '.');
  }

  /** Reativar exige ao menos um exemplar ativo; o backend decide e responde 409 `book_without_active_copy`. */
  protected reactivateBlockReason(book: StaffCatalogBookDetail): string | null {
    return book.copies.some((copy) => copy.is_active)
      ? null
      : 'A obra não tem exemplar ativo: não pode ser reativada.';
  }

  protected askReactivate(book: StaffCatalogBookDetail): void {
    if (!this.canEdit || book.is_active || this.reactivateBlockReason(book)) return;
    this.blocked.set(null);
    this.flow.ask({
      title: `Reativar ${book.title}?`,
      intro:
        'A obra volta a aparecer no acervo ativo e passa a aceitar novos exemplares e operações. Os registros anteriores são preservados.',
      detailsTitle: 'Situação verificada',
      details: [
        book.total_copies === 1
          ? '1 exemplar vinculado'
          : `${book.total_copies} exemplares vinculados`,
        `Exemplares ativos: ${book.copies.filter((copy) => copy.is_active).length}`,
      ],
      confirmLabel: 'Confirmar reativação',
      run: () => this.books.update(book.id, { is_active: true }),
      success: () => `${book.title} foi reativada.`,
    });
  }

  /** Situação lida dos exemplares carregados; a decisão final é do backend, que também confere solicitações e reservas. */
  protected deactivationSituation(book: StaffCatalogBookDetail): string[] {
    const active = book.copies.filter((copy) => copy.is_active);
    const borrowed = active.filter((copy) => copy.status === 'BORROWED');
    const reserved = active.filter((copy) => copy.allocated_for_purchase);
    const lines = [
      book.total_copies === 1
        ? '1 exemplar vinculado'
        : `${book.total_copies} exemplares vinculados`,
    ];
    if (!borrowed.length && !reserved.length) {
      lines.push('Nenhum exemplar emprestado ou reservado para venda');
      return lines;
    }
    for (const copy of borrowed)
      lines.push(`Exemplar ${copy.barcode} emprestado (bloqueia a inativação)`);
    for (const copy of reserved)
      lines.push(`Exemplar ${copy.barcode} reservado para venda (bloqueia a inativação)`);
    return lines;
  }

  protected askDeactivate(book: StaffCatalogBookDetail): void {
    if (!this.canEdit || !book.is_active) return;
    this.blocked.set(null);
    this.flow.ask({
      title: `Inativar ${book.title}?`,
      intro:
        'A obra deixa de aparecer no acervo ativo e não aceita novos exemplares. Os registros anteriores são preservados. A obra pode ser reativada depois, se tiver exemplar ativo. A inativação é bloqueada enquanto houver empréstimo em aberto, solicitação de retirada pendente ou reserva de compra aguardando ou com exemplar destinado.',
      detailsTitle: 'Situação verificada',
      details: this.deactivationSituation(book),
      confirmLabel: 'Confirmar inativação',
      run: () => this.books.update(book.id, { is_active: false }),
      success: () => `${book.title} foi inativada. O histórico foi preservado.`,
      onError: (error) => this.showBookBlock(error),
    });
  }

  /** Motivo exibido junto ao botão desabilitado e em title, para antecipar o botão desabilitado; null quando o backend deve decidir. */
  protected deleteCopyBlockReason(
    book: StaffCatalogBookDetail,
    copy: StaffCatalogCopy,
  ): string | null {
    if (copy.status !== 'AVAILABLE')
      return `Exemplar ${copyStatusLabel(copy).toLowerCase()}: só exemplares disponíveis podem ser excluídos.`;
    if (copy.allocated_for_purchase) return 'Exemplar reservado para venda: não pode ser excluído.';
    if (
      book.is_active &&
      copy.is_active &&
      !book.copies.some((other) => other.id !== copy.id && other.is_active)
    ) {
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
    const reasons = (details.reasons ?? [])
      .map((reason) => reason.message)
      .filter((message): message is string => !!message);
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
      lines: [
        ...positiveEntries(details.counts, COUNT_LABEL),
        ...(details.links ?? []).map(describeLink),
      ],
    });
    return true;
  }
}
