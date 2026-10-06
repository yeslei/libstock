import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';

import { CounterService } from '../../counter/counter.service';
import { adminUser, pendencies } from '../user-fixtures';
import { UserPendenciesComponent } from './user-pendencies.component';

describe('UserPendenciesComponent', () => {
  let counter: jasmine.SpyObj<CounterService>;

  function create(): ComponentFixture<UserPendenciesComponent> {
    const fixture = TestBed.createComponent(UserPendenciesComponent);
    fixture.componentInstance.userId = adminUser().id;
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(async () => {
    counter = jasmine.createSpyObj<CounterService>('CounterService', ['getClientPendencies']);
    await TestBed.configureTestingModule({
      imports: [UserPendenciesComponent],
      providers: [{ provide: CounterService, useValue: counter }],
    }).compileComponents();
  });

  it('consulta a leitura V2 do balcão pelo id do usuário', () => {
    counter.getClientPendencies.and.returnValue(of(pendencies(false)));
    create();
    expect(counter.getClientPendencies).toHaveBeenCalledOnceWith(2);
  });

  it('mostra "Sem pendências ativas" quando não há atraso', () => {
    counter.getClientPendencies.and.returnValue(of(pendencies(false)));
    const text = create().nativeElement.textContent as string;
    expect(text).toContain('Pendências');
    expect(text).toContain('Sem pendências ativas');
  });

  it('lista obra, exemplar, vencimento e dias de atraso, sem ações de alteração', () => {
    counter.getClientPendencies.and.returnValue(of(pendencies(true)));
    const root = create().nativeElement as HTMLElement;
    const text = root.textContent as string;
    expect(text).toContain('Pendência ativa');
    expect(text).toContain('Dom Casmurro');
    expect(text).toContain('EX-7');
    expect(text).toContain('20/09/2026');
    expect(text).toContain('12 dia(s) de atraso');
    expect(text).toContain('consta como penalizado');
    expect(root.querySelectorAll('button').length).toBe(0);
  });

  it('indica carregamento enquanto aguarda', () => {
    counter.getClientPendencies.and.returnValue(new Subject());
    expect(create().nativeElement.textContent).toContain('Consultando pendências');
  });

  it('mostra o erro e permite tentar novamente', () => {
    counter.getClientPendencies.and.returnValues(
      throwError(() => ({ status: 500, detail: 'Falha ao consultar.' })),
      of(pendencies(false)),
    );
    const fixture = create();
    expect(fixture.nativeElement.textContent).toContain('Falha ao consultar.');
    (fixture.nativeElement.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(counter.getClientPendencies).toHaveBeenCalledTimes(2);
    expect(fixture.nativeElement.textContent).toContain('Sem pendências ativas');
  });
});
