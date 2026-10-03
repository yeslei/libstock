import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

/** Contratos de `GET/POST /api/v1/staff/...` (balcão V2). Somente leitura, exceto as quatro confirmações. */
export interface StaffClient {
  readonly id: number;
  readonly name: string;
  readonly email: string;
  readonly is_active: boolean;
  readonly is_penalized: boolean;
  readonly has_overdue_loan: boolean;
  readonly eligible: boolean;
}

export interface StaffBook {
  readonly id: number;
  readonly title: string;
  readonly author: string;
  readonly is_active: boolean;
}

export interface EligibleCopy {
  readonly id: number;
  readonly barcode: string;
  readonly condition: string | null;
}

export interface StaffLoanRequest {
  readonly id: number;
  readonly client: StaffClient;
  readonly book: StaffBook;
  readonly pickup_date: string;
  readonly due_date: string;
  readonly created_at: string;
  readonly eligible_copies: readonly EligibleCopy[];
}

export interface StaffLoan {
  readonly id: number;
  readonly client: StaffClient;
  readonly book: StaffBook;
  readonly copy_id: number;
  readonly copy_barcode: string;
  readonly loan_date: string;
  readonly due_date: string;
  readonly status: 'ACTIVE' | 'OVERDUE';
  readonly days_late: number;
}

export type AllocationBlock =
  | 'NOT_FIRST_IN_QUEUE'
  | 'CLIENT_INELIGIBLE'
  | 'NO_FREE_COPY'
  | 'BOOK_INACTIVE';

export type ReservationStatus = 'WAITING' | 'NOTIFIED';

export interface StaffPurchaseReservation {
  readonly id: number;
  readonly client: StaffClient;
  readonly book: StaffBook;
  readonly status: ReservationStatus;
  readonly queue_position: number | null;
  readonly requested_at: string;
  readonly pickup_date: string | null;
  readonly notified_at: string | null;
  readonly expires_at: string | null;
  readonly expired: boolean;
  readonly allocated_copy_id: number | null;
  readonly allocated_copy_barcode: string | null;
  readonly free_commercial_copies: number;
  readonly can_allocate: boolean;
  readonly allocation_blocked_reason: AllocationBlock | null;
}

/** `GET /api/v1/clients/{id}/pendencies` (já existente; SELLER e ADMINISTRATOR). */
export interface ClientPendencies {
  readonly client_id: number;
  readonly has_pending: boolean;
  readonly is_penalized: boolean;
  readonly overdue_loans: readonly {
    readonly loan_id: number;
    readonly copy_id: number;
    readonly book_id: number;
    readonly book_title: string;
    readonly loan_date: string;
    readonly due_date: string;
  }[];
}

export interface CirculationResult {
  readonly id: number;
}

export interface DeskFilter {
  readonly q?: string;
  readonly clientId?: number | null;
}

const STAFF = '/api/v1/staff';

function params(values: Record<string, string | number | null | undefined>): HttpParams {
  let result = new HttpParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined && value !== '') result = result.set(key, String(value));
  }
  return result;
}

/** Cliente HTTP dedicado ao balcão V2; não toca nos endpoints transacionais antigos (`/loans`, `/sales`). */
@Injectable({ providedIn: 'root' })
export class CounterService {
  private readonly http = inject(HttpClient);

  searchClients(q: string): Observable<StaffClient[]> {
    return this.http.get<StaffClient[]>(`${STAFF}/clients`, { params: params({ q: q.trim() }) });
  }

  getClientPendencies(clientId: number): Observable<ClientPendencies> {
    return this.http.get<ClientPendencies>(`/api/v1/clients/${clientId}/pendencies`);
  }

  listLoanRequests(filter: DeskFilter = {}): Observable<StaffLoanRequest[]> {
    return this.http.get<StaffLoanRequest[]>(`${STAFF}/loan-requests`, {
      params: params({ q: filter.q?.trim(), client_id: filter.clientId }),
    });
  }

  confirmPickup(requestId: number, copyId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/loan-requests/${requestId}/confirm-pickup`, {
      copy_id: copyId,
    });
  }

  listLoans(filter: DeskFilter = {}): Observable<StaffLoan[]> {
    return this.http.get<StaffLoan[]>(`${STAFF}/loans`, {
      params: params({ q: filter.q?.trim(), client_id: filter.clientId }),
    });
  }

  confirmReturn(loanId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/loans/${loanId}/confirm-return`, {});
  }

  listPurchaseReservations(
    filter: DeskFilter & { status?: ReservationStatus | '' } = {},
  ): Observable<StaffPurchaseReservation[]> {
    return this.http.get<StaffPurchaseReservation[]>(`${STAFF}/purchase-reservations`, {
      params: params({ q: filter.q?.trim(), client_id: filter.clientId, status: filter.status }),
    });
  }

  allocatePurchase(bookId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/books/${bookId}/allocate-purchase`, {});
  }

  confirmSale(reservationId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/purchase-reservations/${reservationId}/confirm-sale`, {});
  }
}
