import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AdminUser } from '../models/user.model';
import { UserService } from './user.service';

const USER: AdminUser = {
  id: 7,
  name: 'Ana Souza',
  email: 'ana@example.com',
  role_codes: ['SELLER'],
  is_active: true,
  created_at: '2026-09-01T12:00:00Z',
  updated_at: '2026-09-01T12:00:00Z',
};

describe('UserService', () => {
  let service: UserService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(UserService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista todos os usuários sem filtro', () => {
    service.list().subscribe((users) => expect(users).toEqual([USER]));
    const request = http.expectOne('/api/v1/users');
    expect(request.request.method).toBe('GET');
    request.flush([USER]);
  });

  it('envia o filtro usando o código canônico', () => {
    service.list('SELLER').subscribe();
    const request = http.expectOne('/api/v1/users?role=SELLER');
    expect(request.request.method).toBe('GET');
    request.flush([USER]);
  });

  it('carrega e atualiza um usuário', () => {
    service.get(7).subscribe();
    const getRequest = http.expectOne('/api/v1/users/7');
    getRequest.flush(USER);

    const payload = { name: 'Ana Lima', email: 'lima@example.com', role_code: 'STOCK_KEEPER' as const };
    service.update(7, payload).subscribe();
    const patchRequest = http.expectOne('/api/v1/users/7');
    expect(patchRequest.request.method).toBe('PATCH');
    expect(patchRequest.request.body).toEqual(payload);
    patchRequest.flush({ ...USER, ...payload, role_codes: ['STOCK_KEEPER'] });
  });

  it('inativa um usuário', () => {
    service.inactivate(7).subscribe();
    const request = http.expectOne('/api/v1/users/7/inactivate');
    expect(request.request.method).toBe('PATCH');
    request.flush({ ...USER, is_active: false });
  });
});
