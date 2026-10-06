import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { AdminUser } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { UserManagementComponent } from './user-management.component';

const USERS: AdminUser[] = [
  {
    id: 1,
    name: 'Ana Costa',
    email: 'ana@admin.libstock',
    role_codes: ['ADMINISTRATOR'],
    is_active: true,
    created_at: '2026-09-01T12:00:00Z',
    updated_at: '2026-09-01T12:00:00Z',
  },
  {
    id: 2,
    name: 'João Souza',
    email: 'joao@func.libstock',
    role_codes: ['SELLER'],
    is_active: true,
    created_at: '2026-09-02T12:00:00Z',
    updated_at: '2026-09-02T12:00:00Z',
  },
  {
    id: 3,
    name: 'Carlos Lima',
    email: 'carlos@email.com',
    role_codes: ['USER'],
    is_active: false,
    created_at: '2026-09-03T12:00:00Z',
    updated_at: '2026-09-03T12:00:00Z',
  },
];

describe('UserManagementComponent', () => {
  let fixture: ComponentFixture<UserManagementComponent>;
  let api: jasmine.SpyObj<UserService>;
  let router: jasmine.SpyObj<Router>;

  const root = () => fixture.nativeElement as HTMLElement;
  const rows = () => Array.from(root().querySelectorAll('tbody tr'));
  const buttonsOf = (row: Element) =>
    Array.from(row.querySelectorAll('button')).map((button) => button.textContent?.trim());

  async function create(list = of(USERS)) {
    api = jasmine.createSpyObj<UserService>('UserService', ['list']);
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    api.list.and.returnValue(list);
    await TestBed.configureTestingModule({
      imports: [UserManagementComponent],
      providers: [
        { provide: UserService, useValue: api },
        { provide: Router, useValue: router },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(UserManagementComponent);
    fixture.detectChanges();
  }

  it('lista usuário, e-mail, perfil e status em colunas', async () => {
    await create();
    const headers = Array.from(root().querySelectorAll('th')).map((th) => th.textContent?.trim());
    expect(headers).toEqual(['Usuário', 'E-mail', 'Perfil', 'Status', 'Ações']);
    expect(rows().length).toBe(3);
    const text = rows()[1].textContent as string;
    expect(text).toContain('João Souza');
    expect(text).toContain('joao@func.libstock');
    expect(text).toContain('Vendedor');
    expect(text).toContain('Ativo');
  });

  it('oferece Ver e Editar para ativos e somente Ver para inativos, sem inativar nem excluir na lista', async () => {
    await create();
    expect(buttonsOf(rows()[0])).toEqual(['Ver', 'Editar']);
    expect(buttonsOf(rows()[2])).toEqual(['Ver']);
    expect(root().textContent).not.toContain('Excluir');
    expect(root().textContent).not.toContain('Inativar');
    expect(root().textContent).not.toContain('CPF');
  });

  it('leva Ver e Editar para as rotas de gestão existentes', async () => {
    await create();
    const [view, edit] = Array.from(rows()[1].querySelectorAll('button'));
    view.click();
    edit.click();
    expect(router.navigate).toHaveBeenCalledWith(['/gestao/usuarios', 2]);
    expect(router.navigate).toHaveBeenCalledWith(['/gestao/usuarios', 2, 'editar']);
  });

  it('leva o cadastro para a tela existente de funcionários', async () => {
    await create();
    const button = Array.from(root().querySelectorAll('button')).find((item) =>
      item.textContent?.includes('Cadastrar novo usuário'),
    )!;
    button.click();
    expect(router.navigate).toHaveBeenCalledWith(['/gestao/funcionarios']);
  });

  it('busca por nome ou e-mail e mostra estado vazio sem resultado', async () => {
    await create();
    const search = root().querySelector('#user-search') as HTMLInputElement;
    search.value = 'CARLOS@';
    search.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(rows().length).toBe(1);
    expect(rows()[0].textContent).toContain('Carlos Lima');
    search.value = 'inexistente';
    search.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(rows().length).toBe(0);
    expect(root().textContent).toContain('Nenhum usuário encontrado.');
  });

  it('filtra pelo código canônico do perfil', async () => {
    await create();
    const select = root().querySelector('#role-filter') as HTMLSelectElement;
    select.value = 'SELLER';
    select.dispatchEvent(new Event('change'));
    expect(api.list).toHaveBeenCalledWith('SELLER');
  });

  it('mostra estado vazio da base', async () => {
    await create(of([]));
    expect(root().textContent).toContain('Nenhum usuário cadastrado.');
  });

  it('indica carregamento', async () => {
    await create(new Subject<AdminUser[]>() as never);
    expect(root().textContent).toContain('Carregando usuários');
  });

  it('mostra erro com nova tentativa', async () => {
    await create(throwError(() => ({ status: 500, detail: 'Falha ao listar.' })) as never);
    expect(root().textContent).toContain('Falha ao listar.');
    api.list.and.returnValue(of(USERS));
    const retry = Array.from(root().querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Tentar novamente')!;
    retry.click();
    fixture.detectChanges();
    expect(rows().length).toBe(3);
  });
});
