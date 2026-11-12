import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AuditLogFilters, AuditLogPage } from '../models/audit-log.model';

const AUDIT_API = '/api/v1/audit-logs';

@Injectable({ providedIn: 'root' })
export class AuditLogService {
  private readonly http = inject(HttpClient);

  list(filters: AuditLogFilters = {}): Observable<AuditLogPage> {
    let params = new HttpParams();
    if (filters.entityType) params = params.set('entity_type', filters.entityType);
    if (filters.entityId) params = params.set('entity_id', filters.entityId);
    if (filters.operation) params = params.set('operation', filters.operation);
    if (filters.employeeId !== undefined) params = params.set('employee_id', filters.employeeId);
    if (filters.dateFrom) params = params.set('date_from', filters.dateFrom);
    if (filters.dateTo) params = params.set('date_to', filters.dateTo);
    if (filters.limit !== undefined) params = params.set('limit', filters.limit);
    if (filters.offset !== undefined) params = params.set('offset', filters.offset);
    return this.http.get<AuditLogPage>(AUDIT_API, { params });
  }
}
