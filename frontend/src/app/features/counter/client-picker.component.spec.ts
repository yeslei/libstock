import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { ClientPickerComponent } from './client-picker.component';
import { CounterService, StaffClient } from './counter.service';

const client = (over: Partial<StaffClient> = {}): StaffClient => ({
  id: 3, name: 'Maria Silva', email: 'maria@x.dev', is_active: true, is_penalized: false, has_overdue_loan: false, eligible: true, ...over,
});

function setup(mode: 'loan' | 'sale', service: jasmine.SpyObj<CounterService>) {
  TestBed.configureTestingModule({ imports: [ClientPickerComponent], providers: [{ provide: CounterService, useValue: service }] });
  const fixture = TestBed.createComponent(ClientPickerComponent);
  fixture.componentRef.setInput('mode', mode);
  fixture.detectChanges();
  return { fixture, root: fixture.nativeElement as HTMLElement };
}

function filter(fixture: ComponentFixture<unknown>, root: HTMLElement, term: string) {
  const input = root.querySelector('input') as HTMLInputElement;
  input.value = term;
  input.dispatchEvent(new Event('input'));
  input.closest('form')!.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

describe('Seleção de cliente do balcão', () => {
  it('carrega a lista padrão, filtra com 2+ caracteres e emite o cliente escolhido', () => {
    const service = jasmine.createSpyObj<CounterService>('CounterService', ['searchClients']);
    service.searchClients.and.returnValue(of([client()]));
    const { fixture, root } = setup('loan', service);
    const picked: StaffClient[] = [];
    fixture.componentInstance.picked.subscribe((c) => picked.push(c));
    expect(service.searchClients).toHaveBeenCalledOnceWith(undefined);
    expect(root.textContent).toContain('Maria Silva');
    expect(root.textContent).toContain('apto');
    filter(fixture, root, 'm');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('ao menos 2 caracteres');
    expect(service.searchClients).toHaveBeenCalledTimes(1);
    filter(fixture, root, 'maria');
    expect(service.searchClients).toHaveBeenCalledWith('maria');
    (root.querySelector('.result button') as HTMLButtonElement).click();
    expect(picked.map((c) => c.id)).toEqual([3]);
  });

  it('mostra erro com nova tentativa e vazio distinto do filtro sem resultado', () => {
    const service = jasmine.createSpyObj<CounterService>('CounterService', ['searchClients']);
    service.searchClients.and.returnValue(throwError(() => ({ detail: 'Falha ao consultar.' })));
    const { fixture, root } = setup('sale', service);
    expect(root.textContent).toContain('Falha ao consultar.');
    service.searchClients.and.returnValue(of([]));
    (Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Tentar novamente') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(root.textContent).toContain('Nenhum cliente ativo cadastrado.');
    filter(fixture, root, 'zz');
    expect(root.textContent).toContain('Nenhum cliente encontrado.');
  });
});
