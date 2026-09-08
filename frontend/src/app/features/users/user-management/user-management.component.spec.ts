import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';

import { AdminUser } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { UserService } from '../../../core/services/user.service';
import { UserManagementComponent } from './user-management.component';

const USERS: AdminUser[] = [
  {
    id: 1,
    name: 'Administrador Atual',
    email: 'admin@example.com',
    role_codes: ['ADMINISTRATOR'],
    is_active: true,
    created_at: '2026-09-01T12:00:00Z',
    updated_at: '2026-09-01T12:00:00Z',
  },
  {
    id: 2,
    name: 'Vendedora',
    email: 'venda@example.com',
    role_codes: ['SELLER'],
    is_active: true,
    created_at: '2026-09-02T12:00:00Z',
    updated_at: '2026-09-02T12:00:00Z',
  },
];

describe('UserManagementComponent', () => {
  let fixture: ComponentFixture<UserManagementComponent>;
  let api: jasmine.SpyObj<UserService>;
  let router: jasmine.SpyObj<Router>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<UserService>('UserService', ['list', 'inactivate']);
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    api.list.and.returnValue(of(USERS));
    api.inactivate.and.returnValue(of({ ...USERS[1], is_active: false }));

    await TestBed.configureTestingModule({
      imports: [UserManagementComponent],
      providers: [
        { provide: UserService, useValue: api },
        { provide: Router, useValue: router },
        { provide: AuthService, useValue: { currentUser: USERS[0] } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(UserManagementComponent);
    fixture.detectChanges();
  });

  it('lista usuários com rótulos amigáveis e exclusão desabilitada', () => {
    const text = fixture.nativeElement.textContent as string;
    const deleteButtons = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).filter((button) => button.textContent?.trim() === 'Excluir');

    expect(text).toContain('Administrador');
    expect(text).toContain('Vendedor');
    expect(deleteButtons.length).toBe(2);
    expect(deleteButtons.every((button) => button.disabled)).toBeTrue();
  });

  it('leva o cadastro para a tela existente de funcionários', () => {
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((item) => item.textContent?.includes('Cadastrar novo usuário'))!;

    button.click();

    expect(router.navigate).toHaveBeenCalledWith(['/gestao/funcionarios']);
  });

  it('filtra pelo código canônico do cargo', () => {
    const select = fixture.nativeElement.querySelector('#role-filter') as HTMLSelectElement;
    select.value = 'SELLER';
    select.dispatchEvent(new Event('change'));

    expect(api.list).toHaveBeenCalledWith('SELLER');
  });

  it('confirma e inativa outro usuário', () => {
    spyOn(window, 'confirm').and.returnValue(true);
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    );
    const inactivate = buttons.find((button) => button.textContent?.trim() === 'Inativar' && !button.disabled)!;

    inactivate.click();

    expect(api.inactivate).toHaveBeenCalledWith(2);
  });
});
