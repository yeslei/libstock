import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { errorInterceptor } from '../../../core/interceptors/error.interceptor';
import { CreateEmployeeComponent } from './create-employee.component';

describe('CreateEmployeeComponent', () => {
  let fixture: ComponentFixture<CreateEmployeeComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateEmployeeComponent],
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(CreateEmployeeComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function input(id: string): HTMLInputElement {
    return fixture.nativeElement.querySelector(`#${id}`) as HTMLInputElement;
  }

  function select(id: string): HTMLSelectElement {
    return fixture.nativeElement.querySelector(`#${id}`) as HTMLSelectElement;
  }

  function fillValidForm(): void {
    input('employee-name').value = '  Maria Silva  ';
    input('employee-name').dispatchEvent(new Event('input'));
    input('employee-email').value = '  maria@exemplo.com  ';
    input('employee-email').dispatchEvent(new Event('input'));
    input('employee-password').value = 'senhasegura';
    input('employee-password').dispatchEvent(new Event('input'));
    select('employee-access-level').value = 'SELLER';
    select('employee-access-level').dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function submit(): void {
    fixture.debugElement.query(By.css('form')).triggerEventHandler('ngSubmit');
    fixture.detectChanges();
  }

  function pageText(): string {
    return (fixture.nativeElement as HTMLElement).textContent ?? '';
  }

  it('formulário inválido não chama a API', () => {
    submit();

    http.expectNone('/api/v1/employees/');
    expect(document.activeElement?.id).toBe('employee-name');
  });

  it('exibe as quatro opções canônicas de nível de acesso', () => {
    const values = Array.from(select('employee-access-level').options).map((option) => option.value);

    expect(values).toContain('ATTENDANT');
    expect(values).toContain('SELLER');
    expect(values).toContain('STOCK_KEEPER');
    expect(values).toContain('MANAGER');
  });

  it('não oferece ADMINISTRATOR como papel cadastrável', () => {
    const values = Array.from(select('employee-access-level').options).map((option) => option.value);

    expect(values).not.toContain('ADMINISTRATOR');
  });

  it('envia o payload normalizado no contrato esperado', () => {
    fillValidForm();
    submit();

    const request = http.expectOne('/api/v1/employees/');
    expect(request.request.body).toEqual({
      name: 'Maria Silva',
      email: 'maria@exemplo.com',
      password: 'senhasegura',
      accessLevel: 'SELLER',
    });
  });

  it('impede submissão duplicada enquanto a requisição está em andamento', () => {
    fillValidForm();
    submit();
    submit();

    const requests = http.match('/api/v1/employees/');
    expect(requests.length).toBe(1);
    expect(requests[0].request.method).toBe('POST');
    expect(requests[0].request.body).toEqual({
      name: 'Maria Silva',
      email: 'maria@exemplo.com',
      password: 'senhasegura',
      accessLevel: 'SELLER',
    });

    requests[0].flush(
      {
        id: 123,
        name: 'Maria Silva',
        email: 'maria@exemplo.com',
        role_code: 'SELLER',
      },
      { status: 201, statusText: 'Created' },
    );
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('button[type="submit"]').disabled).toBeFalse();
  });

  it('exibe sucesso e limpa o formulário após 201', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      {
        id: 123,
        name: 'Maria Silva',
        email: 'maria@exemplo.com',
        role_code: 'SELLER',
      },
      { status: 201, statusText: 'Created' },
    );
    fixture.detectChanges();

    expect(pageText()).toContain('Funcionário cadastrado com sucesso.');
    expect(pageText()).toContain('Maria Silva');
    expect(pageText()).toContain('maria@exemplo.com');
    expect(pageText()).toContain('SELLER');
    expect(input('employee-name').value).toBe('');
    expect(input('employee-email').value).toBe('');
    expect(input('employee-password').value).toBe('');
    expect(select('employee-access-level').value).toBe('');
  });

  it('mostra mensagem específica para 409 duplicate_email', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      { detail: 'duplicado', code: 'duplicate_email' },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();

    expect(pageText()).toContain('Este e-mail já está cadastrado.');
  });

  it('mostra mensagem específica para 409 duplicate_employee_code', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      { detail: 'duplicado', code: 'duplicate_employee_code' },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();

    expect(pageText()).toContain('Não foi possível gerar um código único');
  });

  it('mostra falta de permissão para 403', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      { detail: 'negado', code: 'permission_denied' },
      { status: 403, statusText: 'Forbidden' },
    );
    fixture.detectChanges();

    expect(pageText()).toContain('Você não tem permissão para cadastrar funcionários.');
  });

  it('apresenta 422 de forma legível', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      { detail: 'Papel inválido.', code: 'invalid_role' },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(pageText()).toContain('Papel inválido.');
  });

  it('apresenta 422 do FastAPI sem exibir JSON bruto', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      {
        detail: [
          {
            type: 'value_error',
            loc: ['body', 'accessLevel'],
            msg: 'Input should be a valid role',
          },
        ],
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(pageText()).toContain('Confira os dados informados e tente novamente.');
    expect(pageText()).not.toContain('value_error');
    expect(pageText()).not.toContain('[object Object]');
  });

  it('finaliza o envio, preserva valores e permite nova tentativa após falha', () => {
    fillValidForm();
    submit();

    http.expectOne('/api/v1/employees/').flush(
      { detail: 'falha', code: 'unexpected_error' },
      { status: 500, statusText: 'Server Error' },
    );
    fixture.detectChanges();

    expect(input('employee-name').value).toBe('Maria Silva');
    expect(input('employee-email').value).toBe('  maria@exemplo.com  ');
    expect(input('employee-password').value).toBe('senhasegura');
    expect(select('employee-access-level').value).toBe('SELLER');
    expect(fixture.nativeElement.querySelector('button[type="submit"]').disabled).toBeFalse();

    submit();

    const retry = http.expectOne('/api/v1/employees/');
    expect(retry.request.body).toEqual({
      name: 'Maria Silva',
      email: 'maria@exemplo.com',
      password: 'senhasegura',
      accessLevel: 'SELLER',
    });
    retry.flush(
      {
        id: 124,
        name: 'Maria Silva',
        email: 'maria@exemplo.com',
        role_code: 'SELLER',
      },
      { status: 201, statusText: 'Created' },
    );
  });
});
