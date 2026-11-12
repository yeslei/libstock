import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ApiError } from '../../../core/models/auth.model';
import { AuditLogItem } from '../../../core/models/audit-log.model';
import { AuditLogService } from '../../../core/services/audit-log.service';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';

const ENTITY_OPTIONS = [
  { value: 'books', label: 'Obras' },
  { value: 'copies', label: 'Exemplares' },
  { value: 'loans', label: 'Empréstimos' },
  { value: 'sales', label: 'Vendas' },
  { value: 'purchase_reservations', label: 'Reservas' },
  { value: 'users', label: 'Usuários' },
  { value: 'profiles', label: 'Perfis' },
  { value: 'clients', label: 'Clientes' },
] as const;

const OPERATION_OPTIONS = [
  { value: 'INSERT', label: 'Criação' },
  { value: 'UPDATE', label: 'Alteração' },
  { value: 'DELETE', label: 'Exclusão' },
  { value: 'CANCEL', label: 'Cancelamento' },
  { value: 'PASSWORD_RESET', label: 'Redefinição de senha' },
] as const;

const PAGE_SIZE = 50;

@Component({
  selector: 'app-audit-log-page',
  standalone: true,
  imports: [AlertComponent, SpinnerComponent],
  templateUrl: './audit-log-page.component.html',
  styleUrl: './audit-log-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuditLogPageComponent implements OnInit {
  private readonly api = inject(AuditLogService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly entityOptions = ENTITY_OPTIONS;
  protected readonly operationOptions = OPERATION_OPTIONS;
  protected readonly pageSize = PAGE_SIZE;
  protected readonly items = signal<readonly AuditLogItem[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly entityType = signal('');
  protected readonly operation = signal('');
  protected readonly dateFrom = signal('');
  protected readonly dateTo = signal('');
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly expanded = signal<number | null>(null);
  protected readonly page = computed(() => Math.floor(this.offset() / PAGE_SIZE) + 1);
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / PAGE_SIZE)));

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .list({
        entityType: this.entityType() || undefined,
        operation: this.operation() || undefined,
        dateFrom: this.dateFrom() || undefined,
        dateTo: this.dateTo() || undefined,
        limit: PAGE_SIZE,
        offset: this.offset(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.items.set(page.items);
          this.total.set(page.total);
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.items.set([]);
          this.error.set(error.detail || 'Não foi possível carregar a auditoria.');
          this.loading.set(false);
        },
      });
  }

  protected filterEntity(event: Event): void {
    this.entityType.set((event.target as HTMLSelectElement).value);
    this.reloadFromFirstPage();
  }

  protected filterOperation(event: Event): void {
    this.operation.set((event.target as HTMLSelectElement).value);
    this.reloadFromFirstPage();
  }

  protected filterDateFrom(event: Event): void {
    this.dateFrom.set((event.target as HTMLInputElement).value);
    this.reloadFromFirstPage();
  }

  protected filterDateTo(event: Event): void {
    this.dateTo.set((event.target as HTMLInputElement).value);
    this.reloadFromFirstPage();
  }

  protected previousPage(): void {
    if (this.offset() === 0) return;
    this.offset.set(Math.max(0, this.offset() - PAGE_SIZE));
    this.load();
  }

  protected nextPage(): void {
    if (this.offset() + PAGE_SIZE >= this.total()) return;
    this.offset.set(this.offset() + PAGE_SIZE);
    this.load();
  }

  protected toggle(item: AuditLogItem): void {
    this.expanded.update((current) => (current === item.id ? null : item.id));
  }

  protected formatDate(value: string): string {
    return new Intl.DateTimeFormat('pt-BR', {
      dateStyle: 'short',
      timeStyle: 'short',
      timeZone: 'America/Sao_Paulo',
    }).format(new Date(value));
  }

  protected entityLabel(value: string): string {
    return ENTITY_OPTIONS.find((option) => option.value === value)?.label ?? value;
  }

  protected operationLabel(value: string): string {
    return OPERATION_OPTIONS.find((option) => option.value === value)?.label ?? value;
  }

  protected oldPayload(item: AuditLogItem): string {
    return item.old_value ? JSON.stringify(item.old_value, null, 2) : '—';
  }

  protected newPayload(item: AuditLogItem): string {
    return item.new_value ? JSON.stringify(item.new_value, null, 2) : '—';
  }

  private reloadFromFirstPage(): void {
    this.offset.set(0);
    this.expanded.set(null);
    this.load();
  }
}
