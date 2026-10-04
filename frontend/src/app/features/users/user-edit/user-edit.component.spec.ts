import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { AdminUser } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { UserService } from '../../../core/services/user.service';
import { SnackbarService } from '../../../shared/components/snackbar/snackbar.service';
import { CounterService } from '../../counter/counter.service';
import { adminUser, pendencies } from '../user-fixtures';
import { UserEditComponent } from './user-edit.component';

describe('UserEditComponent', () => {
  let api: jasmine.SpyObj<UserService>;
  let counter: jasmine.SpyObj<CounterService>;
  let snackbar: SnackbarService;

  function configure(currentUserId: number, routeId: string): ComponentFixture<UserEditComponent> {
    TestBed.configureTestingModule({
      imports: [UserEditComponent],
      providers: [
        provideRouter([]),
        { provide: UserService, useValue: api },
        { provide: CounterService, useValue: counter },
        { provide: AuthService, useValue: { currentUser: { id: currentUserId, role_codes: ['ADMINISTRATOR'] } } },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => routeId } } } },
      ],
    });
    snackbar = TestBed.inject(SnackbarService);
    const fixture = TestBed.createComponent(UserEditComponent);
    fixture.detectChanges();
    return fixture;
  }

  function create(user: AdminUser = adminUser(), currentUserId = 1): ComponentFixture<UserEditComponent> {
    api.get.and.returnValue(of(user));
    return configure(currentUserId, String(user.id));
  }

  const root = (fixture: ComponentFixture<unknown>) => fixture.nativeElement as HTMLElement;
  const button = (fixture: ComponentFixture<unknown>, label: string) =>
    Array.from(root(fixture).querySelectorAll('button')).find((b) => b.textContent?.trim() === label) as
      | HTMLButtonElement
      | undefined;
  const setValue = (fixture: ComponentFixture<unknown>, selector: string, value: string, event = 'input') => {
    const control = root(fixture).querySelector(selector) as HTMLInputElement | HTMLSelectElement;
    control.value = value;
    control.dispatchEvent(new Event(event));
    fixture.detectChanges();
  };

  beforeEach(() => {
    api = jasmine.createSpyObj<UserService>('UserService', ['get', 'update', 'inactivate']);
    counter = jasmine.createSpyObj<CounterService>('CounterService', ['getClientPendencies']);
    counter.getClientPendencies.and.returnValue(of(pendencies(false)));
  });

  afterEach(() => snackbar?.dismiss());

  it('mostra cabeçalho, dados, perfil e pendências, sem CPF', () => {
    const fixture = create();
    const text = root(fixture).textContent as string;
    expect(root(fixture).querySelector('h1')?.textContent).toContain('Maria Silva');
    expect(text).toContain('Cliente • Ativo');
    expect((root(fixture).querySelector('#user-email') as HTMLInputElement).value).toBe('maria@email.com');
    expect((root(fixture).querySelector('#user-role') as HTMLSelectElement).value).toBe('USER');
    expect(text).toContain('Sem pendências ativas');
    expect(text).not.toContain('CPF');
  });

  it('mostra pendência com atraso somente para leitura', () => {
    counter.getClientPendencies.and.returnValue(of(pendencies(true)));
    const text = root(create()).textContent as string;
    expect(text).toContain('12 dia(s) de atraso');
  });

  it('não consulta pendências de funcionário', () => {
    create(adminUser({ role_codes: ['SELLER'] } as Partial<AdminUser>));
    expect(counter.getClientPendencies).not.toHaveBeenCalled();
  });

  it('salva nome e e-mail sem confirmação e só mostra sucesso após a resposta', () => {
    const fixture = create();
    const response = new Subject<AdminUser>();
    api.update.and.returnValue(response);
    setValue(fixture, '#user-name', ' Maria S. Silva ');
    button(fixture, 'Salvar alterações')!.click();
    fixture.detectChanges();
    expect(api.update).toHaveBeenCalledOnceWith(2, { name: 'Maria S. Silva', email: 'maria@email.com', role_code: 'USER' });
    expect(snackbar.notification()).toBeNull();
    response.next(adminUser({ name: 'Maria S. Silva' }));
    fixture.detectChanges();
    expect(snackbar.notification()?.message).toBe('Usuário atualizado com sucesso.');
    expect(snackbar.notification()?.variant).toBe('success');
    expect(root(fixture).querySelector('h1')?.textContent).toContain('Maria S. Silva');
  });

  it('bloqueia o duplo envio enquanto a requisição está em curso', () => {
    const fixture = create();
    api.update.and.returnValue(new Subject<AdminUser>());
    button(fixture, 'Salvar alterações')!.click();
    fixture.detectChanges();
    expect(button(fixture, 'Inativar usuário')!.disabled).toBeTrue();
    root(fixture).querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(api.update).toHaveBeenCalledTimes(1);
  });

  it('valida entrada sem chamar a API', () => {
    const fixture = create();
    setValue(fixture, '#user-email', 'invalido');
    button(fixture, 'Salvar alterações')!.click();
    fixture.detectChanges();
    expect(api.update).not.toHaveBeenCalled();
    expect(root(fixture).textContent).toContain('Digite um e-mail válido');
  });

  it('mostra erro de domínio (e-mail duplicado) e não anuncia sucesso', () => {
    const fixture = create();
    api.update.and.returnValue(
      throwError(() => ({ status: 409, code: 'email_already_exists', detail: 'E-mail já cadastrado.' })),
    );
    setValue(fixture, '#user-email', 'outra@email.com');
    button(fixture, 'Salvar alterações')!.click();
    fixture.detectChanges();
    expect(snackbar.notification()?.message).toBe('E-mail já cadastrado.');
    expect(snackbar.notification()?.variant).toBe('error');
    expect(button(fixture, 'Salvar alterações')!.disabled).toBeFalse();
  });

  it('pede confirmação antes de alterar o perfil e permite cancelar', fakeAsync(() => {
    const fixture = create();
    setValue(fixture, '#user-role', 'SELLER', 'change');
    button(fixture, 'Salvar alterações')!.click();
    fixture.detectChanges();
    tick();
    expect(api.update).not.toHaveBeenCalled();
    expect(root(fixture).textContent).toContain('Alterar perfil?');
    expect(root(fixture).textContent).toContain('de Cliente para Vendedor');
    button(fixture, 'Cancelar')!.click();
    fixture.detectChanges();
    expect(api.update).not.toHaveBeenCalled();
    expect(root(fixture).textContent).not.toContain('Alterar perfil?');
  }));

  it('envia a mudança de perfil somente após confirmar', fakeAsync(() => {
    const fixture = create();
    api.update.and.returnValue(of(adminUser({ role_codes: ['SELLER'] } as Partial<AdminUser>)));
    setValue(fixture, '#user-role', 'SELLER', 'change');
    button(fixture, 'Salvar alterações')!.click();
    fixture.detectChanges();
    tick();
    button(fixture, 'Confirmar alteração')!.click();
    fixture.detectChanges();
    expect(api.update).toHaveBeenCalledOnceWith(2, { name: 'Maria Silva', email: 'maria@email.com', role_code: 'SELLER' });
    expect(snackbar.notification()?.variant).toBe('success');
    expect(root(fixture).textContent).toContain('Vendedor • Ativo');
  }));

  it('abre o cartão de confirmação de inativação e cancela sem chamar a API', fakeAsync(() => {
    const fixture = create();
    button(fixture, 'Inativar usuário')!.click();
    fixture.detectChanges();
    tick();
    const text = root(fixture).textContent as string;
    expect(text).toContain('Inativar usuário?');
    expect(text).toContain('Maria Silva perderá acesso ao sistema.');
    expect(text).toContain('O histórico permanecerá preservado.');
    button(fixture, 'Cancelar')!.click();
    fixture.detectChanges();
    expect(api.inactivate).not.toHaveBeenCalled();
    expect(root(fixture).textContent).not.toContain('Confirmar inativação');
  }));

  it('inativa só após confirmar, com bloqueio de duplo clique e sucesso após 2xx', fakeAsync(() => {
    const fixture = create();
    const response = new Subject<AdminUser>();
    api.inactivate.and.returnValue(response);
    button(fixture, 'Inativar usuário')!.click();
    fixture.detectChanges();
    tick();
    expect(api.inactivate).not.toHaveBeenCalled();
    const confirm = button(fixture, 'Confirmar inativação')!;
    confirm.click();
    confirm.click();
    fixture.detectChanges();
    expect(api.inactivate).toHaveBeenCalledOnceWith(2);
    expect(snackbar.notification()).toBeNull();
    response.next(adminUser({ is_active: false }));
    fixture.detectChanges();
    expect(snackbar.notification()?.message).toBe('Maria Silva foi inativado com sucesso.');
    expect(root(fixture).textContent).toContain('Cliente • Inativo');
    expect(button(fixture, 'Salvar alterações')).toBeUndefined();
    expect(button(fixture, 'Inativar usuário')).toBeUndefined();
    expect((root(fixture).querySelector('#user-name') as HTMLInputElement).disabled).toBeTrue();
  }));

  it('mostra erro de domínio da inativação e mantém o usuário ativo', fakeAsync(() => {
    const fixture = create();
    api.inactivate.and.returnValue(
      throwError(() => ({
        status: 409,
        code: 'last_active_administrator',
        detail: 'Não é possível inativar o último administrador ativo.',
      })),
    );
    button(fixture, 'Inativar usuário')!.click();
    fixture.detectChanges();
    tick();
    button(fixture, 'Confirmar inativação')!.click();
    fixture.detectChanges();
    expect(snackbar.notification()?.message).toBe('Não é possível inativar o último administrador ativo.');
    expect(snackbar.notification()?.variant).toBe('error');
    expect(root(fixture).textContent).toContain('Cliente • Ativo');
  }));

  it('não oferece inativar a própria conta nem trocar o próprio perfil de administrador', () => {
    const fixture = create(adminUser({ id: 1, role_codes: ['ADMINISTRATOR'] } as Partial<AdminUser>), 1);
    expect(button(fixture, 'Inativar usuário')).toBeUndefined();
    expect((root(fixture).querySelector('#user-role') as HTMLSelectElement).disabled).toBeTrue();
  });

  it('mostra erro de carregamento', () => {
    api.get.and.returnValue(throwError(() => ({ status: 404, detail: 'Usuário não encontrado.' })));
    const fixture = configure(1, '9');
    expect(root(fixture).textContent).toContain('Usuário não encontrado.');
  });

  it('rejeita identificador inválido', () => {
    const fixture = configure(1, 'abc');
    expect(api.get).not.toHaveBeenCalled();
    expect(root(fixture).textContent).toContain('Identificador de usuário inválido.');
  });
});
