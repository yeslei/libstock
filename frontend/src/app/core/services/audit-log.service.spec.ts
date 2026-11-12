import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuditLogPage } from '../models/audit-log.model';
import { AuditLogService } from './audit-log.service';

const PAGE: AuditLogPage = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
};

describe('AuditLogService', () => {
  let service: AuditLogService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuditLogService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta sem filtros', () => {
    service.list().subscribe((page) => expect(page).toEqual(PAGE));
    const request = http.expectOne('/api/v1/audit-logs');
    expect(request.request.method).toBe('GET');
    request.flush(PAGE);
  });

  it('envia todos os filtros com os nomes do contrato', () => {
    service
      .list({
        entityType: 'copies',
        entityId: '10',
        operation: 'UPDATE',
        employeeId: 4,
        dateFrom: '2026-11-01',
        dateTo: '2026-11-10',
        limit: 25,
        offset: 50,
      })
      .subscribe();

    const request = http.expectOne(
      '/api/v1/audit-logs?entity_type=copies&entity_id=10&operation=UPDATE&employee_id=4&date_from=2026-11-01&date_to=2026-11-10&limit=25&offset=50',
    );
    expect(request.request.method).toBe('GET');
    request.flush(PAGE);
  });

  it('não envia filtros vazios', () => {
    service.list({ entityType: '', operation: '', dateFrom: '', limit: 50, offset: 0 }).subscribe();

    const request = http.expectOne('/api/v1/audit-logs?limit=50&offset=0');
    request.flush(PAGE);
  });
});
