import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface TrackingItem {
  id: number;
  book_id: number;
  title: string;
  author: string;
  cover_url: string | null;
  status: 'AWAITING_PICKUP' | 'ACTIVE' | 'OVERDUE' | 'WAITING' | 'NOTIFIED';
  copy_barcode: string | null;
  pickup_date: string | null;
  due_date: string | null;
  days_late: number;
  queue_position: number | null;
  available_since: string | null;
  expires_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class ClientTrackingService {
  private readonly http = inject(HttpClient);
  getLoans() { return this.http.get<TrackingItem[]>('/api/v1/loans/me'); }
  getReservations() { return this.http.get<TrackingItem[]>('/api/v1/purchase-reservations/me'); }
}
