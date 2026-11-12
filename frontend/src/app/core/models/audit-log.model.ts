/** Registro imutável de auditoria exposto por `GET /api/v1/audit-logs`. */
export interface AuditLogItem {
  readonly id: number;
  readonly occurred_at: string;
  readonly employee_id: number | null;
  readonly employee_name: string | null;
  readonly entity_type: string;
  readonly entity_id: string;
  readonly operation: string;
  readonly old_value: Readonly<Record<string, unknown>> | null;
  readonly new_value: Readonly<Record<string, unknown>> | null;
}

export interface AuditLogPage {
  readonly items: readonly AuditLogItem[];
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

/** Filtros aceitos pela API; campos vazios não são enviados. */
export interface AuditLogFilters {
  readonly entityType?: string;
  readonly entityId?: string;
  readonly operation?: string;
  readonly employeeId?: number;
  readonly dateFrom?: string;
  readonly dateTo?: string;
  readonly limit?: number;
  readonly offset?: number;
}
