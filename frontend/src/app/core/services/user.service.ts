import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AdminUser, RoleCode, UpdateUserRequest } from '../models/user.model';

const USERS_API = '/api/v1/users';

@Injectable({ providedIn: 'root' })
export class UserService {
  private readonly http = inject(HttpClient);

  list(role?: RoleCode): Observable<AdminUser[]> {
    const params = role ? new HttpParams().set('role', role) : undefined;
    return this.http.get<AdminUser[]>(USERS_API, { params });
  }

  get(userId: number): Observable<AdminUser> {
    return this.http.get<AdminUser>(`${USERS_API}/${userId}`);
  }

  update(userId: number, payload: UpdateUserRequest): Observable<AdminUser> {
    return this.http.patch<AdminUser>(`${USERS_API}/${userId}`, payload);
  }

  inactivate(userId: number): Observable<AdminUser> {
    return this.http.patch<AdminUser>(`${USERS_API}/${userId}/inactivate`, null);
  }
}
