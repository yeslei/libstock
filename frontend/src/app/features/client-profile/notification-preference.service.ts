import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export type NotificationChannel = 'EMAIL' | 'IN_APP';
export interface NotificationPreference { channel: NotificationChannel; email: string; }

@Injectable({ providedIn: 'root' })
export class NotificationPreferenceService {
  private readonly http = inject(HttpClient);
  private readonly endpoint = '/api/v1/me/notification-preferences';
  get() { return this.http.get<NotificationPreference>(this.endpoint); }
  update(channel: NotificationChannel) { return this.http.patch<NotificationPreference>(this.endpoint, { channel }); }
}
