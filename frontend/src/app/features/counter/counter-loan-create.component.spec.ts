import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../app.routes';
import { CounterLoanCreateComponent, isLoanable } from './counter-loan-create.component';
import { CounterService, LoanRegistration, StaffClient, StaffCopyLookup } from './counter.service';

const client = (over: Partial<StaffClient> = {}): StaffClient => ({
  id: 3, name: 'Maria Silva', email: 'maria@x.dev', is_active: true, is_penalized: false, has_overdue_loan: false, eligible: true, ...over,
});

const copy = (over: Partial<StaffCopyLookup> = {}): StaffCopyLookup => ({
  id: 9, barcode: '00101', destination: 'DIDACTIC', status: 'AVAILABLE', condition: null, sale_price: null,
  book: { id: 4, title: 'Dom Casmurro', author: 'Machado', isbn: null, is_active: true },
  free: true, free_commercial_copies: 0, sellable: false, sale_block_reason: 'DIDACTIC', ...over,
});

const created: LoanRegistration = {
  id: 77, client_id: 3, copy_id: 9, employee_id: 2, loan_date: '2026-10-03T15:00:00Z', due_date: '2026-10-18T15:00:00Z',
  returned_at: null, status: 'OPEN',
};

function setup(configure: (service: jasmine.SpyObj<CounterService>) => void = () => undefined) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['searchClients', 'lookupCopies', 'registerLoan']);
  service.searchClients.and.returnValue(of([client()]));
  service.lookupCopies.and.returnValue(of([copy()]));
  configure(service);
  TestBed.configureTestingModule({
    imports: [CounterLoanCreateComponent],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }],
  });
  const fixture = TestBed.createComponent(CounterLoanCreateComponent);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

function type(fixture: ComponentFixture<unknown>, input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event('input'));
  fixture.detectChanges();
}

function submit(fixture: ComponentFixture<unknown>, form: HTMLFormElement) {
  form.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

function button(root: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`Botão não encontrado: ${label}`);
  return found as HTMLButtonElement;
}

function click(fixture: ComponentFixture<unknown>, element: HTMLElement) {
  element.click();
  fixture.detectChanges();
}

async function flush(fixture: ComponentFixture<unknown>) {
  await Promise.resolve();
  fixture.detectChanges();
}

/** Escolhe o cliente e o exemplar pela interface. */
function fill(fixture: ComponentFixture<unknown>, root: HTMLElement) {
  type(fixture, root.querySelector('#loan-client') as HTMLInputElement, 'maria');
  submit(fixture, root.querySelector('#loan-client')!.closest('form') as HTMLFormElement);
  click(fixture, button(root, 'Selecionar'));
  type(fixture, root.querySelector('#loan-copy') as HTMLInputElement, 'casmurro');
  submit(fixture, root.querySelector('#loan-copy')!.closest('form') as HTMLFormElement);
  click(fixture, button(root, 'Selecionar'));
}

describe('Balcão: novo empréstimo', () => {
  it('abre o formulário sem consultar nada e sem permitir revisar', () => {
    const { root, service } = setup();
    expect(root.querySelector('h1')?.textContent).toBe('Novo empréstimo no balcão');
    expect(service.searchClients).not.toHaveBeenCalled();
    expect(service.lookupCopies).not.toHaveBeenCalled();
    expect(button(root, 'Revisar empréstimo').disabled).toBeTrue();
    expect(root.textContent).toContain('Devolução prevista: calculada automaticamente ao registrar');
    expect(root.textContent).not.toContain('15 dias');
  });

  it('exige ao menos 2 caracteres para buscar o cliente e o termo para o exemplar', () => {
    const { fixture, root, service } = setup();
    type(fixture, root.querySelector('#loan-client') as HTMLInputElement, 'm');
    submit(fixture, root.querySelector('#loan-client')!.closest('form') as HTMLFormElement);
    expect(service.searchClients).not.toHaveBeenCalled();
    expect(root.querySelector('#loan-client-error')?.textContent).toContain('ao menos 2 caracteres');
    submit(fixture, root.querySelector('#loan-copy')!.closest('form') as HTMLFormElement);
    expect(service.lookupCopies).not.toHaveBeenCalled();
    expect(root.querySelector('#loan-copy-error')?.textContent).toContain('Informe o código do exemplar');
  });

  it('seleciona cliente apto e exemplar didático livre e habilita a revisão', () => {
    const { fixture, root, service } = setup();
    fill(fixture, root);
    expect(service.searchClients).toHaveBeenCalledOnceWith('maria');
    expect(service.lookupCopies).toHaveBeenCalledOnceWith('casmurro');
    expect(root.textContent).toContain('Cliente apto');
    expect(root.textContent).toContain('Conta ativa · sem pendências.');
    expect(root.textContent).toContain('#00101');
    expect(button(root, 'Revisar empréstimo').disabled).toBeFalse();
  });

  it('antecipa o bloqueio de cliente inelegível sem chamar o POST', () => {
    const { fixture, root, service } = setup((s) =>
      s.searchClients.and.returnValue(of([client({ eligible: false, has_overdue_loan: true })])));
    fill(fixture, root);
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Cliente não apto para empréstimo');
    expect(root.textContent).toContain('empréstimo em atraso');
    expect(button(root, 'Revisar empréstimo').disabled).toBeTrue();
    expect(service.registerLoan).not.toHaveBeenCalled();
  });

  it('só oferece exemplar didático livre de obra ativa e explica os demais', () => {
    expect(isLoanable(copy())).toBeTrue();
    expect(isLoanable(copy({ destination: 'COMMERCIAL' }))).toBeFalse();
    expect(isLoanable(copy({ free: false, status: 'BORROWED' }))).toBeFalse();
    const { fixture, root } = setup((s) =>
      s.lookupCopies.and.returnValue(of([
        copy({ id: 1, barcode: 'C-1', destination: 'COMMERCIAL', free: true }),
        copy({ id: 2, barcode: 'D-2', status: 'BORROWED', free: false }),
        copy({ id: 3, barcode: 'D-3' , book: { id: 4, title: 'Inativa', author: 'x', isbn: null, is_active: false } }),
        copy({ id: 4, barcode: 'D-4' }),
      ])));
    type(fixture, root.querySelector('#loan-copy') as HTMLInputElement, 'x');
    submit(fixture, root.querySelector('#loan-copy')!.closest('form') as HTMLFormElement);
    const items = Array.from(root.querySelectorAll('.results li'));
    expect(items.map((li) => li.querySelector('button')!.disabled)).toEqual([true, true, true, false]);
    const text = items.map((li) => li.textContent?.replace(/\s+/g, ' '));
    expect(text[0]).toContain('exemplar destinado à venda');
    expect(text[1]).toContain('emprestado');
    expect(text[2]).toContain('obra inativa');
    expect(text[3]).toContain('Disponível · destinado a empréstimo');
  });

  it('mostra a revisão com os dados escolhidos, sem calcular prazo, e não chama o POST ao revisar', () => {
    const { fixture, root, service } = setup();
    fill(fixture, root);
    click(fixture, button(root, 'Revisar empréstimo'));
    expect(root.querySelector('h1')?.textContent).toBe('Revisar empréstimo');
    const text = root.textContent?.replace(/\s+/g, ' ');
    expect(text).toContain('Cliente: Maria Silva · maria@x.dev');
    expect(text).toContain('Livro: Dom Casmurro · Exemplar #00101');
    expect(text).toContain('Devolução prevista: valor calculado pelo sistema ao registrar');
    expect(text).toContain('o exemplar ficará Emprestado');
    expect(service.registerLoan).not.toHaveBeenCalled();
    click(fixture, button(root, 'Voltar'));
    expect(root.querySelector('h1')?.textContent).toBe('Novo empréstimo no balcão');
    expect(root.textContent).toContain('#00101');
  });

  it('registra após a confirmação, bloqueia envio duplicado e só mostra sucesso após 2xx', async () => {
    const pending = new Subject<LoanRegistration>();
    const { fixture, root, service } = setup((s) => s.registerLoan.and.returnValue(pending));
    fill(fixture, root);
    click(fixture, button(root, 'Revisar empréstimo'));
    click(fixture, button(root, 'Confirmar empréstimo'));
    expect(service.registerLoan).toHaveBeenCalledOnceWith(3, 9);
    const confirm = button(root, 'Confirmando…');
    expect(confirm.disabled).toBeTrue();
    confirm.click();
    fixture.detectChanges();
    expect(service.registerLoan).toHaveBeenCalledTimes(1);
    expect(root.textContent).not.toContain('registrado com sucesso');
    pending.next(created);
    pending.complete();
    await flush(fixture);
    expect(root.querySelector('h1')?.textContent).toBe('Empréstimo registrado');
    const text = root.textContent?.replace(/\s+/g, ' ');
    expect(text).toContain('Empréstimo registrado com sucesso');
    expect(text).toContain('Entregue o exemplar #00101 ao cliente.');
    expect(text).toContain('Maria Silva · Dom Casmurro · #00101');
    // Datas do backend, no fuso de America/Sao_Paulo (-03:00), sem cálculo no frontend.
    expect(text).toContain('Retirada: 03/10/2026');
    expect(text).toContain('Devolução prevista: 18/10/2026');
    expect(text).toContain('Empréstimo nº 77 · Status do exemplar: Emprestado');
    expect(text).not.toContain('comprovante');
  });

  it('volta ao formulário vazio em "Novo empréstimo"', async () => {
    const { fixture, root } = setup((s) => s.registerLoan.and.returnValue(of(created)));
    fill(fixture, root);
    click(fixture, button(root, 'Revisar empréstimo'));
    click(fixture, button(root, 'Confirmar empréstimo'));
    await flush(fixture);
    click(fixture, button(root, 'Novo empréstimo'));
    expect(root.querySelector('h1')?.textContent).toBe('Novo empréstimo no balcão');
    expect(button(root, 'Revisar empréstimo').disabled).toBeTrue();
    expect((root.querySelector('#loan-client') as HTMLInputElement).value).toBe('');
  });

  it('mostra o bloqueio de cliente com a mensagem do backend, sem sucesso, e permite trocar o cliente', async () => {
    const { fixture, root } = setup((s) =>
      s.registerLoan.and.returnValue(throwError(() => ({
        status: 409, code: 'client_has_pending', detail: 'Cliente possui pendência ativa e não pode realizar a operação.',
      }))));
    fill(fixture, root);
    click(fixture, button(root, 'Revisar empréstimo'));
    click(fixture, button(root, 'Confirmar empréstimo'));
    await flush(fixture);
    expect(root.querySelector('h1')?.textContent).toBe('Empréstimo bloqueado');
    const alert = root.querySelector('[role="alert"]')!.textContent!.replace(/\s+/g, ' ');
    expect(alert).toContain('Cliente não apto para empréstimo');
    expect(alert).toContain('Cliente possui pendência ativa e não pode realizar a operação.');
    expect(alert).toContain('Nenhum empréstimo foi registrado.');
    expect(root.textContent).not.toContain('registrado com sucesso');
    expect(root.querySelector('a.btn--primary')?.getAttribute('href')).toBe('/balcao/clientes');
    click(fixture, button(root, 'Selecionar outro cliente'));
    expect(root.querySelector('h1')?.textContent).toBe('Novo empréstimo no balcão');
    expect(root.querySelector('#loan-client')).not.toBeNull();
    expect(root.textContent).toContain('#00101');
  });

  it('mostra o bloqueio de exemplar indisponível e refaz a busca ao atualizar a seleção', async () => {
    const { fixture, root, service } = setup((s) =>
      s.registerLoan.and.returnValue(throwError(() => ({ status: 409, detail: 'Exemplar não está disponível para empréstimo.' }))));
    fill(fixture, root);
    click(fixture, button(root, 'Revisar empréstimo'));
    click(fixture, button(root, 'Confirmar empréstimo'));
    await flush(fixture);
    expect(root.querySelector('h1')?.textContent).toBe('Empréstimo bloqueado');
    const alert = root.querySelector('[role="alert"]')!.textContent!.replace(/\s+/g, ' ');
    expect(alert).toContain('Exemplar indisponível para empréstimo');
    expect(alert).toContain('Exemplar não está disponível para empréstimo.');
    expect(root.textContent).toContain('atualize a seleção antes de tentar novamente');
    click(fixture, button(root, 'Atualizar seleção'));
    expect(service.lookupCopies).toHaveBeenCalledTimes(2);
    expect(service.lookupCopies.calls.mostRecent().args).toEqual(['casmurro']);
    expect(button(root, 'Revisar empréstimo').disabled).toBeTrue();
  });

  it('trata 404 de exemplar como bloqueio e mantém a revisão em falhas inesperadas', async () => {
    const first = setup((s) => s.registerLoan.and.returnValue(throwError(() => ({ status: 404, detail: 'Exemplar não encontrado ou inativo.' }))));
    fill(first.fixture, first.root);
    click(first.fixture, button(first.root, 'Revisar empréstimo'));
    click(first.fixture, button(first.root, 'Confirmar empréstimo'));
    await flush(first.fixture);
    expect(first.root.textContent).toContain('Exemplar não encontrado ou inativo.');
    TestBed.resetTestingModule();

    const second = setup((s) => s.registerLoan.and.returnValue(throwError(() => ({ status: 500, detail: 'Não foi possível registrar o empréstimo.' }))));
    fill(second.fixture, second.root);
    click(second.fixture, button(second.root, 'Revisar empréstimo'));
    click(second.fixture, button(second.root, 'Confirmar empréstimo'));
    await flush(second.fixture);
    expect(second.root.querySelector('h1')?.textContent).toBe('Revisar empréstimo');
    expect(second.root.querySelector('app-save-failure')?.textContent).toContain('Não foi possível salvar');
    expect(second.root.querySelector('app-save-failure')?.textContent).toContain('Consultar empréstimos ativos');
    expect(snackbarMessage()).toBe('');
    expect(second.service.registerLoan).toHaveBeenCalledTimes(1);
    expect(button(second.root, 'Confirmar empréstimo').disabled).toBeFalse();
  });
});

describe('Rota do empréstimo direto no balcão', () => {
  it('declara /balcao/emprestimos/novo para a tela de novo empréstimo', async () => {
    const children = routes.find((r) => r.path === 'balcao')?.children ?? [];
    const route = children.find((r) => r.path === 'emprestimos/novo');
    expect(await route!.loadComponent!()).toBe(CounterLoanCreateComponent);
  });
});
