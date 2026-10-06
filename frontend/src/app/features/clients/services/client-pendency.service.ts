import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ClientPenaltyUpdate, ClientPendency } from '../models/client-pendency.model';

@Injectable({ providedIn: 'root' })
export class ClientPendencyService {
  private readonly http = inject(HttpClient);
  private readonly endpoint = '/api/v1/clients';

  get(clientId: number): Observable<ClientPendency> {
    return this.http.get<ClientPendency>(`${this.endpoint}/${clientId}/pendencies`);
  }

  updatePenalty(clientId: number, payload: ClientPenaltyUpdate): Observable<ClientPendency> {
    return this.http.patch<ClientPendency>(`${this.endpoint}/${clientId}/penalty`, payload);
  }
}
