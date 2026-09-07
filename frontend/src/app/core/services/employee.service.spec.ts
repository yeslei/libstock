import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CreateEmployeeRequest, CreateEmployeeResponse } from '../models/employee.model';
import { EmployeeService } from './employee.service';

describe('EmployeeService', () => {
  let service: EmployeeService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(EmployeeService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('envia o payload tipado exatamente no contrato do backend', () => {
    const payload: CreateEmployeeRequest = {
      name: 'Ana Souza',
      email: 'ana@exemplo.com',
      password: 'senhaforte',
      accessLevel: 'ATTENDANT',
    };
    const response: CreateEmployeeResponse = {
      id: 123,
      name: 'Ana Souza',
      email: 'ana@exemplo.com',
      role_code: 'ATTENDANT',
    };
    const received: CreateEmployeeResponse[] = [];

    service.create(payload).subscribe((employee) => {
      received.push(employee);
    });

    const request = http.expectOne('/api/v1/employees/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    request.flush(response, { status: 201, statusText: 'Created' });

    expect(received).toEqual([response]);
  });
});
