import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, finalize, switchMap } from 'rxjs';

import { ApiError } from '../../core/models/auth.model';
import { LoadState } from '../../core/models/load-state.model';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { businessToday } from './business-date';
import {
  CLIENT_SEARCH_LIMIT,
  COPY_LOOKUP_LIMIT,
  CounterService,
  LoanRegistration,
  StaffClient,
  StaffCopyLookup,
} from './counter.service';
import { toLoadState } from './desk-flow';
import { errorMessage, ineligibleReasons } from './desk-panel';

type Step = 'form' | 'review' | 'done' | 'blocked';
type BlockKind = 'client' | 'copy';

/** Códigos de domínio do cliente devolvidos por `POST /api/v1/loans/` (BUSINESS_RULES, seção Empréstimo). */
const CLIENT_BLOCK_CODES: readonly string[] = ['client_not_found', 'client_inactive', 'client_has_pending'];

interface Blocked {
  readonly kind: BlockKind;
  readonly message: string;
  readonly clientName: string;
}

interface Completed {
  readonly loan: LoanRegistration;
  readonly client: StaffClient;
  readonly copy: StaffCopyLookup;
}

const NOT_LOANABLE: Readonly<Record<string, string>> = {
  BORROWED: 'emprestado',
  RESERVED: 'reservado',
  SOLD: 'vendido',
  INACTIVE: 'inativo',
};

/** Exemplar didático livre (mesma definição de disponibilidade da retirada V2) de obra ativa. */
export function isLoanable(copy: StaffCopyLookup): boolean {
  return copy.destination === 'DIDACTIC' && copy.free && copy.book.is_active;
}

function notLoanableReason(copy: StaffCopyLookup): string {
  if (copy.destination === 'COMMERCIAL') return 'exemplar destinado à venda';
  if (!copy.book.is_active) return 'obra inativa';
  return NOT_LOANABLE[copy.status] ?? 'indisponível no momento';
}

/**
 * Complemento 06 (proposta condicional, EAP 1.2.9–1.2.13; incluído por decisão do responsável): empréstimo direto
 * no balcão, sem solicitação prévia. Cliente por `GET /staff/clients`, exemplar por `GET /staff/copies`
 * e registro por `POST /api/v1/loans/`. O prazo é calculado pelo backend e a tela só exibe o que ele retorna.
 * A elegibilidade antecipada usa `eligible` do backend; os erros de domínio reais levam ao estado bloqueado.
 */
@Component({
  selector: 'app-counter-loan-create',
  standalone: true,
  imports: [DatePipe, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter-loan-create.component.html',
  styleUrl: './counter-loan-create.component.scss',
})
export class CounterLoanCreateComponent {
  private readonly service = inject(CounterService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly clientSearches = new Subject<string>();
  private readonly copySearches = new Subject<string>();

  protected readonly ineligibleReasons = ineligibleReasons;
  protected readonly isLoanable = isLoanable;
  protected readonly notLoanableReason = notLoanableReason;
  protected readonly clientLimit = CLIENT_SEARCH_LIMIT;
  protected readonly copyLimit = COPY_LOOKUP_LIMIT;
  protected readonly today = (() => {
    const [year, month, day] = businessToday().split('-');
    return `${day}/${month}/${year}`;
  })();

  protected readonly step = signal<Step>('form');
  protected readonly clientTerm = signal('');
  protected readonly clientError = signal<string | null>(null);
  protected readonly clientState = signal<LoadState<readonly StaffClient[]> | null>(null);
  protected readonly client = signal<StaffClient | null>(null);
  protected readonly copyTerm = signal('');
  protected readonly copyError = signal<string | null>(null);
  protected readonly copyState = signal<LoadState<readonly StaffCopyLookup[]> | null>(null);
  protected readonly copy = signal<StaffCopyLookup | null>(null);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly blocked = signal<Blocked | null>(null);
  protected readonly completed = signal<Completed | null>(null);
  /** Termo da última busca de exemplar, reutilizado ao atualizar a seleção. */
  private lastCopyTerm = '';

  /** Só é possível revisar com cliente apto (`eligible` do backend) e exemplar didático livre. */
  protected readonly canReview = computed(() => {
    const client = this.client();
    const copy = this.copy();
    return !!client && client.eligible && !!copy && isLoanable(copy);
  });

  constructor() {
    this.clientSearches
      .pipe(
        switchMap((term) => toLoadState(this.service.searchClients(term), 'Não foi possível buscar os clientes. Tente novamente.')),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.clientState.set(state));
    this.copySearches
      .pipe(
        switchMap((term) => toLoadState(this.service.lookupCopies(term), 'Não foi possível buscar os exemplares. Tente novamente.')),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.copyState.set(state));
  }

  protected setClientTerm(event: Event): void {
    this.clientTerm.set((event.target as HTMLInputElement).value);
    this.clientError.set(null);
  }

  protected searchClients(event: Event): void {
    event.preventDefault();
    const term = this.clientTerm().trim();
    if (term.length < 2) {
      this.clientError.set('Informe ao menos 2 caracteres do nome ou do e-mail.');
      return;
    }
    this.clientSearches.next(term);
  }

  protected selectClient(client: StaffClient): void {
    this.client.set(client);
    this.clientState.set(null);
  }

  protected changeClient(): void {
    this.client.set(null);
  }

  protected setCopyTerm(event: Event): void {
    this.copyTerm.set((event.target as HTMLInputElement).value);
    this.copyError.set(null);
  }

  protected searchCopies(event: Event): void {
    event.preventDefault();
    const term = this.copyTerm().trim();
    if (!term) {
      this.copyError.set('Informe o código do exemplar, o ISBN ou o título.');
      return;
    }
    this.lastCopyTerm = term;
    this.copySearches.next(term);
  }

  protected selectCopy(copy: StaffCopyLookup): void {
    if (!isLoanable(copy)) return;
    this.copy.set(copy);
    this.copyState.set(null);
  }

  protected changeCopy(): void {
    this.copy.set(null);
  }

  protected review(): void {
    if (!this.canReview()) return;
    this.error.set(null);
    this.go('review');
  }

  protected back(): void {
    if (this.submitting()) return;
    this.error.set(null);
    this.go('form');
  }

  protected confirm(): void {
    const client = this.client();
    const copy = this.copy();
    if (this.submitting() || !client || !copy || !this.canReview()) return;
    this.submitting.set(true);
    this.error.set(null);
    this.service
      .registerLoan(client.id, copy.id)
      .pipe(
        finalize(() => this.submitting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (loan) => {
          this.completed.set({ loan, client, copy });
          this.go('done');
        },
        error: (error: unknown) => this.fail(error, client),
      });
  }

  /** Erros de domínio (cliente, exemplar) levam ao estado bloqueado; falhas inesperadas mantêm a revisão. */
  private fail(error: unknown, client: StaffClient): void {
    const { status, code } = (error ?? {}) as Partial<ApiError>;
    const detail = errorMessage(error, '');
    if (code && CLIENT_BLOCK_CODES.includes(code)) {
      this.block('client', detail, client);
    } else if (status === 404 || status === 409) {
      this.block('copy', detail || 'O exemplar não está disponível para empréstimo.', client);
    } else {
      this.error.set(
        detail ||
          'Não foi possível registrar o empréstimo. Confira em Empréstimos ativos se ele foi registrado antes de tentar novamente.',
      );
      this.focusHeading();
    }
  }

  private block(kind: BlockKind, message: string, client: StaffClient): void {
    this.blocked.set({
      kind,
      message: message || 'O cliente não está apto para empréstimo.',
      clientName: client.name,
    });
    this.go('blocked');
  }

  /** "Selecionar outro cliente": volta ao formulário sem cliente, mantendo o exemplar. */
  protected chooseAnotherClient(): void {
    this.client.set(null);
    this.clientState.set(null);
    this.blocked.set(null);
    this.go('form');
  }

  /** "Atualizar seleção": o exemplar pode ter mudado de situação; a busca é refeita e a escolha descartada. */
  protected refreshSelection(): void {
    this.copy.set(null);
    this.blocked.set(null);
    this.copyState.set(null);
    if (this.lastCopyTerm) this.copySearches.next(this.lastCopyTerm);
    this.go('form');
  }

  protected reset(): void {
    this.client.set(null);
    this.copy.set(null);
    this.clientState.set(null);
    this.copyState.set(null);
    this.clientTerm.set('');
    this.copyTerm.set('');
    this.lastCopyTerm = '';
    this.completed.set(null);
    this.blocked.set(null);
    this.error.set(null);
    this.go('form');
  }

  private go(step: Step): void {
    this.step.set(step);
    this.focusHeading();
  }

  private focusHeading(): void {
    queueMicrotask(() => this.host.nativeElement.querySelector<HTMLElement>('h1')?.focus());
  }
}
