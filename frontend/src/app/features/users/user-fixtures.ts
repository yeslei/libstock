import { AdminUser } from '../../core/models/user.model';
import { ClientPendencies } from '../counter/counter.service';

export function adminUser(overrides: Partial<AdminUser> = {}): AdminUser {
  return {
    id: 2,
    name: 'Maria Silva',
    email: 'maria@email.com',
    role_codes: ['USER'],
    is_active: true,
    created_at: '2026-09-02T12:00:00Z',
    updated_at: '2026-09-02T12:00:00Z',
    ...overrides,
  };
}

export function pendencies(overdue = false): ClientPendencies {
  return {
    client: {
      id: 2, name: 'Maria Silva', email: 'maria@email.com', is_active: true,
      is_penalized: overdue, has_overdue_loan: overdue, eligible: !overdue,
    },
    overdue_loans: overdue
      ? [{
          id: 9,
          client: { id: 2, name: 'Maria Silva', email: 'maria@email.com', is_active: true, is_penalized: true, has_overdue_loan: true, eligible: false },
          book: { id: 5, title: 'Dom Casmurro', author: 'Machado de Assis', is_active: true },
          copy_id: 7, copy_barcode: 'EX-7', loan_date: '2026-09-01T12:00:00-03:00',
          due_date: '2026-09-20T12:00:00-03:00', status: 'OVERDUE', days_late: 12,
        }]
      : [],
  } as unknown as ClientPendencies;
}
