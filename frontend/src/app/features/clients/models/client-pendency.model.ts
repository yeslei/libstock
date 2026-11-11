export type PenaltyAction = 'APPLY' | 'REMOVE';

export interface OverdueLoan {
  readonly loan_id: number;
  readonly copy_id: number;
  readonly book_id: number;
  readonly book_title: string;
  readonly loan_date: string;
  readonly due_date: string;
}

export interface ClientPendency {
  readonly client_id: number;
  readonly has_pending: boolean;
  readonly is_penalized: boolean;
  readonly overdue_loans: OverdueLoan[];
}

export interface ClientPenaltyUpdate {
  readonly action: PenaltyAction;
  readonly reason: string;
}

export interface ReturnReminder {
  readonly id: number;
  readonly loan_id: number;
  readonly client_id: number;
  readonly channel: 'IN_APP' | 'EMAIL';
  readonly status: 'PENDING' | 'SENT' | 'READ' | 'FAILED';
  readonly subject: string;
  readonly message: string;
  readonly created_at: string;
}
