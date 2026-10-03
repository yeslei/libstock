import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface LoanRequestResponse {
  readonly id: number;
  readonly book_id: number;
  readonly pickup_date: string;
  readonly due_date: string;
  readonly status: 'PENDING';
  readonly created_at: string;
}

export type PurchaseRequestResponse = Omit<LoanRequestResponse, 'due_date'>;

export interface PurchaseReservationResponse {
  readonly id: number;
  readonly book_id: number;
  readonly status: 'WAITING';
  readonly queue_position: number;
}

@Injectable({ providedIn: 'root' })
export class ClientRequestsService {
  private readonly http = inject(HttpClient);

  requestLoan(book_id: number, pickup_date: string) {
    return this.http.post<LoanRequestResponse>('/api/v1/loan-requests', { book_id, pickup_date });
  }

  requestPurchase(book_id: number, pickup_date: string) {
    return this.http.post<PurchaseRequestResponse>('/api/v1/purchase-requests', { book_id, pickup_date });
  }

  reservePurchase(book_id: number) {
    return this.http.post<PurchaseReservationResponse>('/api/v1/purchase-reservations', { book_id });
  }
}
