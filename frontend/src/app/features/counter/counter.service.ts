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

/** `GET /api/v1/staff/clients/{id}/pendencies`: somente leitura, atraso pela regra V2. */
export interface ClientPendencies {
  readonly client: StaffClient;
  readonly overdue_loans: readonly StaffLoan[];
}

/** `GET /api/v1/staff/dashboard`: indicadores somente leitura do Painel (definições em BUSINESS_RULES, seção 21). */
export interface StaffDashboard {
  readonly active_loans: number;
  readonly returns_today: number;
  readonly waiting_reservations: number;
  readonly pendencies: number;
}

export type CopyDestination = 'DIDACTIC' | 'COMMERCIAL';
export type CopyStatus = 'AVAILABLE' | 'BORROWED' | 'RESERVED' | 'SOLD' | 'INACTIVE';

/** `GET /api/v1/staff/books`: obra com a contagem de exemplares ativos e não vendidos. */
export interface StaffCatalogBook {
  readonly id: number;
  readonly title: string;
  readonly author: string;
  readonly isbn: string | null;
  readonly genre: string | null;
  readonly is_active: boolean;
  readonly total_copies: number;
  readonly didactic_copies: number;
  readonly commercial_copies: number;
}

export interface StaffCatalogCopy {
  readonly id: number;
  readonly barcode: string;
  readonly destination: CopyDestination;
  readonly status: CopyStatus;
  readonly condition: string | null;
  /** Decimal serializado pela API como texto. */
  readonly sale_price: string | number | null;
  readonly is_active: boolean;
  readonly free: boolean;
  readonly allocated_for_purchase: boolean;
}

export interface StaffCatalogBookDetail extends StaffCatalogBook {
  readonly copies: readonly StaffCatalogCopy[];
}

export type SaleBlock = 'DIDACTIC' | 'NOT_AVAILABLE';

/** `GET /api/v1/staff/copies`: a elegibilidade para venda é decidida no backend. */
export interface StaffCopyLookup {
  readonly id: number;
  readonly barcode: string;
  readonly destination: CopyDestination;
  readonly status: CopyStatus;
  readonly condition: string | null;
  readonly sale_price: string | number | null;
  readonly book: { readonly id: number; readonly title: string; readonly author: string; readonly isbn: string | null; readonly is_active: boolean };
  readonly free: boolean;
  readonly free_commercial_copies: number;
  readonly sellable: boolean;
  readonly sale_block_reason: SaleBlock | null;
}

/** Limites enviados explicitamente para que a tela saiba quando a lista foi truncada. */
export const LIST_LIMIT = 50;
export const CLIENT_SEARCH_LIMIT = 20;
export const COPY_LOOKUP_LIMIT = 20;

/** Item pedido a `POST /api/v1/sales/`; o preço enviado é o do exemplar retornado pelo backend. */
export interface SaleItemRequest {
  readonly copy_id: number;
  /** Decimal em texto, exatamente como a API o entregou (sem conversão para ponto flutuante). */
  readonly unit_price: string;
}

/** Resposta de `POST /api/v1/sales/`: a venda nasce PENDING; nenhum endpoint a confirma ou cancela. */
export interface SaleRegistration {
  readonly id: number;
  readonly client_id: number | null;
  readonly status: 'PENDING' | 'CONFIRMED' | 'CANCELLED';
  readonly total_amount: string | number;
}

/** Resposta de `POST /api/v1/loans/`: prazo e datas calculados pelo backend (o frontend não calcula prazo). */
export interface LoanRegistration {
  readonly id: number;
  readonly client_id: number;
  readonly copy_id: number;
  readonly employee_id: number;
  readonly loan_date: string;
  readonly due_date: string;
  readonly returned_at: string | null;
  readonly status: 'OPEN' | 'RETURNED' | 'CANCELLED';
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

/** Cliente HTTP do balcão: consultas e confirmações V2 em `/staff`. */
@Injectable({ providedIn: 'root' })
export class CounterService {
  private readonly http = inject(HttpClient);

  getDashboard(): Observable<StaffDashboard> {
    return this.http.get<StaffDashboard>(`${STAFF}/dashboard`);
  }

  searchClients(q: string): Observable<StaffClient[]> {
    return this.http.get<StaffClient[]>(`${STAFF}/clients`, { params: params({ q: q.trim(), limit: CLIENT_SEARCH_LIMIT }) });
  }

  getClientPendencies(clientId: number): Observable<ClientPendencies> {
    return this.http.get<ClientPendencies>(`${STAFF}/clients/${clientId}/pendencies`);
  }

  listLoanRequests(filter: DeskFilter = {}): Observable<StaffLoanRequest[]> {
    return this.http.get<StaffLoanRequest[]>(`${STAFF}/loan-requests`, {
      params: params({ q: filter.q?.trim(), client_id: filter.clientId, limit: LIST_LIMIT }),
    });
  }

  confirmPickup(requestId: number, copyId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/loan-requests/${requestId}/confirm-pickup`, {
      copy_id: copyId,
    });
  }

  listCatalogBooks(q: string): Observable<StaffCatalogBook[]> {
    return this.http.get<StaffCatalogBook[]>(`${STAFF}/books`, { params: params({ q: q.trim(), limit: LIST_LIMIT }) });
  }

  getCatalogBook(bookId: number): Observable<StaffCatalogBookDetail> {
    return this.http.get<StaffCatalogBookDetail>(`${STAFF}/books/${bookId}`);
  }

  lookupCopies(q: string): Observable<StaffCopyLookup[]> {
    return this.http.get<StaffCopyLookup[]>(`${STAFF}/copies`, { params: params({ q: q.trim(), limit: COPY_LOOKUP_LIMIT }) });
  }

  /** Registra a venda direta (PENDING). Endpoint existente de `/api/v1/sales`, permitido a SELLER e ADMINISTRATOR. */
  registerSale(copyId: number, unitPrice: string | number): Observable<SaleRegistration> {
    const items: SaleItemRequest[] = [{ copy_id: copyId, unit_price: String(unitPrice) }];
    return this.http.post<SaleRegistration>('/api/v1/sales/', { items });
  }

  /** Registra o empréstimo direto. Endpoint existente de `/api/v1/loans`, permitido a SELLER e ADMINISTRATOR; o prazo é calculado por ele. */
  registerLoan(clientId: number, copyId: number): Observable<LoanRegistration> {
    return this.http.post<LoanRegistration>('/api/v1/loans/', { client_id: clientId, copy_id: copyId });
  }

  listLoans(filter: DeskFilter = {}): Observable<StaffLoan[]> {
    return this.http.get<StaffLoan[]>(`${STAFF}/loans`, {
      params: params({ q: filter.q?.trim(), client_id: filter.clientId, limit: LIST_LIMIT }),
    });
  }

  confirmReturn(loanId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/loans/${loanId}/confirm-return`, {});
  }

  listPurchaseReservations(
    filter: DeskFilter & { status?: ReservationStatus | '' } = {},
  ): Observable<StaffPurchaseReservation[]> {
    return this.http.get<StaffPurchaseReservation[]>(`${STAFF}/purchase-reservations`, {
      params: params({ q: filter.q?.trim(), client_id: filter.clientId, status: filter.status, limit: LIST_LIMIT }),
    });
  }

  allocatePurchase(bookId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/books/${bookId}/allocate-purchase`, {});
  }

  confirmSale(reservationId: number): Observable<CirculationResult> {
    return this.http.post<CirculationResult>(`${STAFF}/purchase-reservations/${reservationId}/confirm-sale`, {});
  }
}
