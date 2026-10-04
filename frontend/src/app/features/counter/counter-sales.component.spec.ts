import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../app.routes';
import { CounterReservationAttendComponent } from './counter-reservation-attend.component';
import { CounterReservationsComponent } from './counter-reservations.component';
import { CounterSalesComponent } from './counter-sales.component';
import { CounterService, SaleRegistration, StaffCopyLookup } from './counter.service';

const copy = (over: Partial<StaffCopyLookup> = {}): StaffCopyLookup => ({
  id: 7, barcode: 'C-007', destination: 'COMMERCIAL', status: 'AVAILABLE', condition: null, sale_price: '38.90',
  book: { id: 4, title: 'Sapiens', author: 'Harari', isbn: '9788525432186', is_active: true },
  free: true, free_commercial_copies: 3, sellable: true, sale_block_reason: null, ...over,
});

const confirmed: SaleRegistration = { id: 12, client_id: null, status: 'CONFIRMED', total_amount: '38.90' };

function setup(configure: (service: jasmine.SpyObj<CounterService>) => void) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['lookupCopies', 'registerSale']);
  configure(service);
  TestBed.configureTestingModule({
    imports: [CounterSalesComponent],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }],
  });
  const fixture = TestBed.createComponent(CounterSalesComponent);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

function click(fixture: ComponentFixture<unknown>, element: HTMLElement) {
  element.click();
  fixture.detectChanges();
}

function button(root: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`Botão não encontrado: ${label}`);
  return found as HTMLButtonElement;
}

function submitSearch(fixture: ComponentFixture<unknown>, root: HTMLElement, term: string) {
  const input = root.querySelector('input[type="search"]') as HTMLInputElement;
  input.value = term;
  input.dispatchEvent(new Event('input'));
  root.querySelector('form')!.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

describe('Balcão: registrar venda', () => {
  const dialog = (root: HTMLElement) => root.querySelector('dialog');
  const submitButton = (root: HTMLElement) => dialog(root)!.querySelector('.confirm__submit') as HTMLButtonElement;

  it('não consulta antes da busca e exige o termo', () => {
    const { fixture, root, service } = setup(() => undefined);
    expect(root.querySelector('h1')?.textContent).toBe('Registrar venda');
    expect(root.querySelector('input')?.getAttribute('placeholder')).toBe('Código do exemplar, ISBN ou título');
    expect(service.lookupCopies).not.toHaveBeenCalled();
    submitSearch(fixture, root, '  ');
    expect(service.lookupCopies).not.toHaveBeenCalled();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Informe o código do exemplar, o ISBN ou o título.');
  });

  it('mostra destinação, disponibilidade, preço e estoque reais do exemplar comercial', () => {
    const { fixture, root, service } = setup((s) => s.lookupCopies.and.returnValue(of([copy()])));
    submitSearch(fixture, root, ' Sapiens ');
    expect(service.lookupCopies).toHaveBeenCalledOnceWith('Sapiens');
    const card = root.querySelector('article')!;
    expect(card.textContent).toContain('Sapiens');
    expect(card.textContent?.replace(/\s+/g, ' ')).toContain('Comercial • Disponível para venda');
    expect(card.textContent).toContain('Exemplar C-007');
    expect(card.textContent).toContain('3 exemplar(es) comercial(is) livre(s)');
    expect(card.textContent?.replace(/ /g, ' ')).toContain('R$ 38,90');
    expect(root.querySelector('input[type="number"]')).toBeNull();
    expect(button(root, 'Registrar venda').disabled).toBeFalse();
  });

  it('bloqueia o exemplar didático sem oferecer venda e sem a nota de desenvolvimento', () => {
    const { fixture, root } = setup((s) => s.lookupCopies.and.returnValue(of([
      copy({ destination: 'DIDACTIC', sale_price: null, sellable: false, sale_block_reason: 'DIDACTIC' }),
    ])));
    submitSearch(fixture, root, 'C-007');
    const card = root.querySelector('article')!;
    expect(card.textContent).toContain('Didático');
    expect(card.textContent).toContain('Venda não permitida. Exemplares didáticos não podem ser vendidos.');
    expect(card.querySelector('button')).toBeNull();
    expect(root.textContent).not.toContain('LEMBRETE');
    expect(root.textContent).not.toContain('XXXXXX');
  });

  it('explica o exemplar indisponível sem botão de venda', () => {
    const { fixture, root } = setup((s) => s.lookupCopies.and.returnValue(of([
      copy({ status: 'BORROWED', free: false, sellable: false, sale_block_reason: 'NOT_AVAILABLE' }),
      copy({ id: 8, barcode: 'C-008', status: 'AVAILABLE', free: false, sellable: false, sale_block_reason: 'NOT_AVAILABLE' }),
    ])));
    submitSearch(fixture, root, 'Sapiens');
    const cards = root.querySelectorAll('article');
    expect(cards[0].textContent).toContain('Indisponível para venda no momento: emprestado.');
    expect(cards[1].textContent).toContain('venda em andamento ou reservado para um cliente');
    expect(root.querySelector('article button')).toBeNull();
  });

  it('não permite registrar sem preço cadastrado', () => {
    const { fixture, root, service } = setup((s) => s.lookupCopies.and.returnValue(of([copy({ sale_price: null })])));
    submitSearch(fixture, root, 'C-007');
    expect(root.textContent).toContain('Sem preço de venda cadastrado');
    expect(button(root, 'Registrar venda').disabled).toBeTrue();
    expect(service.registerSale).not.toHaveBeenCalled();
  });

  it('mostra carregamento, vazio e erro de forma distinta', () => {
    const waiting = new Subject<StaffCopyLookup[]>();
    const { fixture, root, service } = setup((s) => s.lookupCopies.and.returnValue(waiting));
    submitSearch(fixture, root, 'X-1');
    expect(root.textContent).toContain('Buscando exemplares');
    waiting.next([]);
    fixture.detectChanges();
    expect(root.querySelector('.empty')?.textContent).toContain('Nenhum exemplar encontrado para “X-1”');
    service.lookupCopies.and.returnValue(throwError(() => ({ detail: 'Falha ao consultar.' })));
    submitSearch(fixture, root, 'X-2');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Falha ao consultar.');
    expect(root.querySelector('.empty')).toBeNull();
  });

  it('avisa quando o limite de resultados é atingido', () => {
    const many = Array.from({ length: 20 }, (_, i) => copy({ id: i + 1, barcode: `C-${i}` }));
    const { fixture, root } = setup((s) => s.lookupCopies.and.returnValue(of(many)));
    submitSearch(fixture, root, 'Sapiens');
    expect(root.querySelector('.note')?.textContent).toContain('Mostrando os primeiros 20');
  });

  it('pede confirmação antes do POST, informa que a venda será confirmada no ato e cancelar não envia', () => {
    const { fixture, root, service } = setup((s) => s.lookupCopies.and.returnValue(of([copy()])));
    submitSearch(fixture, root, 'C-007');
    click(fixture, button(root, 'Registrar venda'));
    expect(dialog(root)?.textContent).toContain('Registrar venda?');
    expect(dialog(root)?.textContent).toContain('A venda será confirmada no ato e o exemplar ficará vendido.');
    expect(dialog(root)?.textContent).not.toContain('pendente');
    click(fixture, button(root, 'Cancelar'));
    expect(dialog(root)).toBeNull();
    expect(service.registerSale).not.toHaveBeenCalled();
  });

  it('não envia preço, bloqueia duplo envio e só anuncia a venda registrada após o 2xx', () => {
    const response = new Subject<SaleRegistration>();
    const { fixture, root, service } = setup((s) => {
      s.lookupCopies.and.returnValue(of([copy()]));
      s.registerSale.and.returnValue(response);
    });
    submitSearch(fixture, root, 'C-007');
    click(fixture, button(root, 'Registrar venda'));
    const submit = submitButton(root);
    click(fixture, submit);
    click(fixture, submit);
    expect(service.registerSale).toHaveBeenCalledOnceWith(7);
    expect(submit.disabled).toBeTrue();
    expect(snackbarMessage()).toBe('');
    service.lookupCopies.and.returnValue(of([copy({ free: false, sellable: false, sale_block_reason: 'NOT_AVAILABLE', free_commercial_copies: 2 })]));
    response.next(confirmed);
    response.complete();
    fixture.detectChanges();
    expect(dialog(root)).toBeNull();
    const feedback = snackbarMessage() ?? '';
    expect(feedback).toContain('Venda registrada');
    expect(feedback).toContain('C-007 vendido');
    expect(feedback).toContain('38,90');
    expect(feedback).toContain('venda nº 12');
    expect(feedback).not.toMatch(/pendente/i);
    expect(service.lookupCopies).toHaveBeenCalledTimes(2);
    expect(root.querySelector('article button')).toBeNull();
  });

  it('mostra o erro de domínio sem sucesso e refaz a busca', () => {
    const { fixture, root, service } = setup((s) => {
      s.lookupCopies.and.returnValue(of([copy()]));
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Um ou mais exemplares não estão disponíveis para venda.', status: 409 })));
    });
    submitSearch(fixture, root, 'C-007');
    click(fixture, button(root, 'Registrar venda'));
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('não estão disponíveis para venda');
    expect(snackbarMessage()).not.toContain('Venda registrada');
    expect(service.lookupCopies).toHaveBeenCalledTimes(2);
  });

  for (const status of [0, 503]) {
    it(`falha de persistência/rede (${status}) mostra "Não foi possível salvar" sem snackbar nem reenvio`, () => {
      const { fixture, root, service } = setup((s) => {
        s.lookupCopies.and.returnValue(of([copy()]));
        s.registerSale.and.returnValue(throwError(() => ({ status, detail: 'Tivemos um problema no servidor.' })));
      });
      submitSearch(fixture, root, 'C-007');
      click(fixture, button(root, 'Registrar venda'));
      click(fixture, submitButton(root));
      const card = root.querySelector('app-save-failure')!;
      expect(card.textContent).toContain('Não foi possível salvar');
      expect(card.textContent).toContain('Atualize a consulta antes de repetir a operação para evitar registros duplicados.');
      expect(snackbarMessage()).toBe('');
      expect(root.textContent).not.toContain('Venda registrada');
      expect(service.registerSale).toHaveBeenCalledTimes(1);
      expect(service.lookupCopies).toHaveBeenCalledTimes(2);
      click(fixture, button(root, 'Atualizar consulta'));
      expect(service.lookupCopies).toHaveBeenCalledTimes(3);
      expect(service.registerSale).toHaveBeenCalledTimes(1);
      click(fixture, button(root, 'Voltar'));
      expect(root.querySelector('app-save-failure')).toBeNull();
    });
  }

  it('exibe o erro de exemplar sem preço devolvido pelo backend, sem sucesso', () => {
    const { fixture, root } = setup((s) => {
      s.lookupCopies.and.returnValue(of([copy()]));
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Este exemplar comercial não tem preço de venda cadastrado e não pode ser vendido.', code: 'copy_without_price', status: 409 })));
    });
    submitSearch(fixture, root, 'C-007');
    click(fixture, button(root, 'Registrar venda'));
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('não tem preço de venda cadastrado');
    expect(snackbarMessage()).not.toContain('Venda registrada');
  });

  it('exibe o erro de domínio de exemplar didático devolvido pelo backend', () => {
    const { fixture, root } = setup((s) => {
      s.lookupCopies.and.returnValue(of([copy()]));
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Exemplares didáticos não podem ser vendidos.', status: 409 })));
    });
    submitSearch(fixture, root, 'C-007');
    click(fixture, button(root, 'Registrar venda'));
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('Exemplares didáticos não podem ser vendidos.');
    expect(snackbarVariant()).toBe('warning');
  });
});

describe('Rotas de vendas e reservas do balcão', () => {
  const children = routes.find((r) => r.path === 'balcao')?.children ?? [];

  it('libera /balcao/vendas para a venda direta e mantém as reservas em /balcao/reservas', async () => {
    expect(await children.find((r) => r.path === 'vendas')!.loadComponent!()).toBe(CounterSalesComponent);
    expect(await children.find((r) => r.path === 'reservas')!.loadComponent!()).toBe(CounterReservationsComponent);
    expect(await children.find((r) => r.path === 'reservas/:id')!.loadComponent!()).toBe(CounterReservationAttendComponent);
  });
});
