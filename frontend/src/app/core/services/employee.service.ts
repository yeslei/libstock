import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { CreateEmployeeRequest, CreateEmployeeResponse } from '../models/employee.model';

const EMPLOYEES_API = '/api/v1/employees';

@Injectable({ providedIn: 'root' })
export class EmployeeService {
  private readonly http = inject(HttpClient);

  create(payload: CreateEmployeeRequest): Observable<CreateEmployeeResponse> {
    return this.http.post<CreateEmployeeResponse>(`${EMPLOYEES_API}/`, payload);
  }
}
