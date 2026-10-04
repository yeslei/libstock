import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { AdminUser } from '../../../core/models/user.model';
import { UserService } from '../../../core/services/user.service';
import { CounterService } from '../../counter/counter.service';
import { adminUser, pendencies } from '../user-fixtures';
import { UserDetailsComponent } from './user-details.component';

describe('UserDetailsComponent', () => {
  let api: jasmine.SpyObj<UserService>;
  let counter: jasmine.SpyObj<CounterService>;

  function create(id = '2') {
    TestBed.configureTestingModule({
      imports: [UserDetailsComponent],
      providers: [
        provideRouter([]),
        { provide: UserService, useValue: api },
        { provide: CounterService, useValue: counter },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => id } } } },
      ],
    });
    const fixture = TestBed.createComponent(UserDetailsComponent);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(() => {
    api = jasmine.createSpyObj<UserService>('UserService', ['get']);
    counter = jasmine.createSpyObj<CounterService>('CounterService', ['getClientPendencies']);
    api.get.and.returnValue(of(adminUser()));
    counter.getClientPendencies.and.returnValue(of(pendencies(false)));
  });

  it('mostra dados, perfil, status e pendências do cliente, sem campo de CPF', () => {
    const text = create().nativeElement.textContent as string;
    expect(text).toContain('Maria Silva');
    expect(text).toContain('maria@email.com');
    expect(text).toContain('Cliente • Ativo');
    expect(text).toContain('Sem pendências ativas');
    expect(text).not.toContain('CPF');
    expect(counter.getClientPendencies).toHaveBeenCalledWith(2);
  });

  it('mostra pendência com atraso', () => {
    counter.getClientPendencies.and.returnValue(of(pendencies(true)));
    const text = create().nativeElement.textContent as string;
    expect(text).toContain('Pendência ativa');
    expect(text).toContain('12 dia(s) de atraso');
  });

  it('não consulta pendências de quem não é cliente', () => {
    api.get.and.returnValue(of(adminUser({ role_codes: ['SELLER'] } as Partial<AdminUser>)));
    const text = create().nativeElement.textContent as string;
    expect(counter.getClientPendencies).not.toHaveBeenCalled();
    expect(text).toContain('Pendências se aplicam somente a clientes.');
    expect(text).toContain('Vendedor');
  });

  it('oferece edição para ativo', () => {
    const active = create().nativeElement as HTMLElement;
    expect(active.querySelector('a[href="/gestao/usuarios/2/editar"]')).not.toBeNull();
  });

  it('oferece apenas consulta para inativo', () => {
    api.get.and.returnValue(of(adminUser({ is_active: false })));
    const inactive = create().nativeElement as HTMLElement;
    expect(inactive.querySelector('a[href="/gestao/usuarios/2/editar"]')).toBeNull();
    expect(inactive.textContent).toContain('Inativo');
  });

  it('indica carregamento', () => {
    api.get.and.returnValue(new Subject());
    expect(create().nativeElement.textContent).toContain('Carregando usuário');
  });

  it('mostra o erro da API', () => {
    api.get.and.returnValue(throwError(() => ({ status: 404, detail: 'Usuário não encontrado.' })));
    expect(create().nativeElement.textContent).toContain('Usuário não encontrado.');
  });

  it('rejeita identificador inválido sem chamar a API', () => {
    expect(create('abc').nativeElement.textContent).toContain('Identificador de usuário inválido.');
    expect(api.get).not.toHaveBeenCalled();
  });

  it('volta para a listagem', () => {
    const fixture = create();
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    const back = Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((button) => button.textContent?.trim() === 'Voltar')!;
    back.click();
    expect(navigate).toHaveBeenCalledWith(['/gestao/usuarios']);
  });
});
