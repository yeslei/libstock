import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { NotificationChannel } from '../client-profile/notification-preference.service';

export interface ClientNotification {
  id: number;
  reservation_id: number | null;
  type: string;
  channel: NotificationChannel;
  subject: string | null;
  message: string;
  status: 'PENDING' | 'SENT' | 'READ' | 'FAILED';
  created_at: string;
  sent_at: string | null;
  read_at: string | null;
}
export interface NotificationPage { items: ClientNotification[]; next_before_id: number | null; }

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly endpoint = '/api/v1/me/notifications';
  list(beforeId: number | null = null) {
    let params = new HttpParams().set('limit', 20);
    if (beforeId !== null) params = params.set('before_id', beforeId);
    return this.http.get<NotificationPage>(this.endpoint, { params });
  }
  markRead(id: number) { return this.http.patch<ClientNotification>(`${this.endpoint}/${id}/read`, null); }
}
