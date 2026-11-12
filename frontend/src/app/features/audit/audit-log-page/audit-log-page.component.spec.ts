import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';

import { AuditLogPage } from '../../../core/models/audit-log.model';
import { AuditLogService } from '../../../core/services/audit-log.service';
import { AuditLogPageComponent } from './audit-log-page.component';

const PAGE: AuditLogPage = {
  items: [
    {
      id: 1,
      occurred_at: '2026-11-10T12:00:00Z',
      employee_id: 4,
      employee_name: 'Ana Souza',
      entity_type: 'copies',
      entity_id: '10',
      operation: 'UPDATE',
      old_value: { status: 'BORROWED' },
      new_value: { status: 'AVAILABLE' },
    },
    {
      id: 2,
      occurred_at: '2026-11-11T12:00:00Z',
      employee_id: null,
      employee_name: null,
      entity_type: 'purchase_reservations',
      entity_id: '20',
      operation: 'CANCEL',
      old_value: null,
      new_value: { reason: 'desistência' },
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

describe('AuditLogPageComponent', () => {
  let fixture: ComponentFixture<AuditLogPageComponent>;
  let api: jasmine.SpyObj<AuditLogService>;

  const root = () => fixture.nativeElement as HTMLElement;
  const rows = () => Array.from(root().querySelectorAll('tbody tr:not(.audit-detail)'));
  const buttonOf = (row: Element) => row.querySelector('button') as HTMLButtonElement;

  async function create(page: Observable<AuditLogPage> = of(PAGE)) {
    api = jasmine.createSpyObj<AuditLogService>('AuditLogService', ['list']);
    api.list.and.returnValue(page);
    await TestBed.configureTestingModule({
      imports: [AuditLogPageComponent],
      providers: [{ provide: AuditLogService, useValue: api }],
    }).compileComponents();
    fixture = TestBed.createComponent(AuditLogPageComponent);
    fixture.detectChanges();
  }

  it('lista data, funcionário, entidade e operação', async () => {
    await create();
    const headers = Array.from(root().querySelectorAll('th')).map((th) => th.textContent?.trim());
    expect(headers).toEqual(['Data/hora', 'Funcionário', 'Entidade', 'Operação', 'Detalhes']);

    expect(rows().length).toBe(2);
    expect(rows()[0].textContent).toContain('Ana Souza');
    expect(rows()[0].textContent).toContain('Exemplares');
    expect(rows()[0].textContent).toContain('#10');
    expect(rows()[0].textContent).toContain('Alteração');
    expect(rows()[1].textContent).toContain('Sistema');
    expect(rows()[1].textContent).toContain('Reservas');
    expect(rows()[1].textContent).toContain('Cancelamento');
  });

  it('abre e fecha os valores anteriores e novos com acessibilidade', async () => {
    await create();
    const button = buttonOf(rows()[0]);
    expect(button.getAttribute('aria-expanded')).toBe('false');

    button.click();
    fixture.detectChanges();

    expect(buttonOf(rows()[0]).getAttribute('aria-expanded')).toBe('true');
    expect(buttonOf(rows()[0]).textContent).toContain('Ocultar');
    const detail = root().querySelector('#audit-detail-1') as HTMLElement;
    expect(detail.textContent).toContain('Antes');
    expect(detail.textContent).toContain('BORROWED');
    expect(detail.textContent).toContain('Depois');
    expect(detail.textContent).toContain('AVAILABLE');

    buttonOf(rows()[0]).click();
    fixture.detectChanges();
    expect(root().querySelector('#audit-detail-1')).toBeNull();
  });

  it('mostra o estado vazio', async () => {
    await create(of({ items: [], total: 0, limit: 50, offset: 0 }));
    expect(root().textContent).toContain('Nenhum registro encontrado');
  });

  it('mostra o erro e permite tentar novamente', async () => {
    await create(throwError(() => ({ detail: 'Falha na consulta de auditoria.', status: 500 })));
    expect(root().textContent).toContain('Falha na consulta de auditoria.');

    api.list.and.returnValue(of(PAGE));
    const retry = Array.from(root().querySelectorAll('button')).find((item) =>
      item.textContent?.includes('Tentar novamente'),
    ) as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    expect(rows().length).toBe(2);
  });

  it('aplica filtros de entidade, operação e período voltando à primeira página', async () => {
    await create(of({ ...PAGE, total: 120 }));

    const entity = root().querySelector('#audit-entity') as HTMLSelectElement;
    entity.value = 'copies';
    entity.dispatchEvent(new Event('change'));
    expect(api.list).toHaveBeenCalledWith(
      jasmine.objectContaining({ entityType: 'copies', offset: 0, limit: 50 }),
    );

    const operation = root().querySelector('#audit-operation') as HTMLSelectElement;
    operation.value = 'CANCEL';
    operation.dispatchEvent(new Event('change'));
    expect(api.list).toHaveBeenCalledWith(
      jasmine.objectContaining({ operation: 'CANCEL', offset: 0 }),
    );

    const from = root().querySelector('#audit-from') as HTMLInputElement;
    from.value = '2026-11-01';
    from.dispatchEvent(new Event('change'));
    expect(api.list).toHaveBeenCalledWith(
      jasmine.objectContaining({ dateFrom: '2026-11-01', offset: 0 }),
    );

    const to = root().querySelector('#audit-to') as HTMLInputElement;
    to.value = '2026-11-10';
    to.dispatchEvent(new Event('change'));
    expect(api.list).toHaveBeenCalledWith(
      jasmine.objectContaining({ dateTo: '2026-11-10', offset: 0 }),
    );
  });

  it('pagina para frente e para trás', async () => {
    await create(of({ ...PAGE, total: 120 }));

    const next = Array.from(root().querySelectorAll('.audit-pager button')).find((item) =>
      item.textContent?.includes('Próxima'),
    ) as HTMLButtonElement;
    next.click();
    fixture.detectChanges();
    expect(api.list).toHaveBeenCalledWith(jasmine.objectContaining({ offset: 50 }));

    const previous = Array.from(root().querySelectorAll('.audit-pager button')).find((item) =>
      item.textContent?.includes('Anterior'),
    ) as HTMLButtonElement;
    previous.click();
    fixture.detectChanges();
    expect(api.list).toHaveBeenCalledWith(jasmine.objectContaining({ offset: 0 }));
  });
});
