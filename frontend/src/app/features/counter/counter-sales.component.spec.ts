import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { receiptGet, receiptStub } from '../receipts/receipt-testing.spec';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../app.routes';
import { CounterReservationAttendComponent } from './counter-reservation-attend.component';
import { CounterReservationsComponent } from './counter-reservations.component';
import { CounterSalesComponent } from './counter-sales.component';
import { CounterService, SaleRegistration, StaffClient, StaffCopyLookup } from './counter.service';

const copy = (over: Partial<StaffCopyLookup> = {}): StaffCopyLookup => ({
  id: 7, barcode: 'C-007', destination: 'COMMERCIAL', status: 'AVAILABLE', condition: null, sale_price: '38.90',
  book: { id: 4, title: 'Sapiens', author: 'Harari', isbn: '9788525432186', is_active: true },
  free: true, free_commercial_copies: 3, sellable: true, sale_block_reason: null, ...over,
});

const client = (over: Partial<StaffClient> = {}): StaffClient => ({
  id: 3, name: 'Maria Silva', email: 'maria@x.dev', is_active: true, is_penalized: false, has_overdue_loan: false, eligible: true, ...over,
});

const confirmed: SaleRegistration = { id: 12, client_id: 3, status: 'CONFIRMED', total_amount: '38.90' };

function setup(configure: (service: jasmine.SpyObj<CounterService>) => void) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['listCopies', 'searchClients', 'registerSale']);
  service.listCopies.and.returnValue(of([copy()]));
  service.searchClients.and.returnValue(of([client()]));
  configure(service);
  TestBed.configureTestingModule({
    imports: [CounterSalesComponent],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }, receiptStub()],
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
  const input = root.querySelector('#sale-q') as HTMLInputElement;
  input.value = term;
  input.dispatchEvent(new Event('input'));
  input.closest('form')!.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

/** Escolhe o primeiro cliente da lista padrão. */
function pickClient(fixture: ComponentFixture<unknown>, root: HTMLElement) {
  click(fixture, root.querySelector('app-client-picker .result button') as HTMLElement);
}

describe('Balcão: registrar venda', () => {
  const dialog = (root: HTMLElement) => root.querySelector('dialog');
  const submitButton = (root: HTMLElement) => dialog(root)!.querySelector('.confirm__submit') as HTMLButtonElement;

  it('abre listando os exemplares comerciais disponíveis e os clientes ativos, sem exigir busca', () => {
    const { root, service } = setup(() => undefined);
    expect(root.querySelector('h1')?.textContent).toBe('Registrar venda');
    expect(root.querySelector('#sale-q')?.getAttribute('placeholder')).toBe('Filtrar por código, ISBN ou título');
    expect(service.listCopies).toHaveBeenCalledOnceWith({ destination: 'COMMERCIAL', available: true }, '');
    expect(service.searchClients).toHaveBeenCalledOnceWith(undefined);
    expect(root.querySelector('article')?.textContent).toContain('Sapiens');
    expect(root.querySelector('app-client-picker')?.textContent).toContain('Maria Silva');
  });

  it('a busca filtra a lista de comerciais disponíveis enviando q, destination e available', () => {
    const { fixture, root, service } = setup(() => undefined);
    submitSearch(fixture, root, ' Sapiens ');
    expect(service.listCopies).toHaveBeenCalledTimes(2);
    expect(service.listCopies.calls.mostRecent().args).toEqual([{ destination: 'COMMERCIAL', available: true }, 'Sapiens']);
    submitSearch(fixture, root, '  ');
    expect(service.listCopies.calls.mostRecent().args).toEqual([{ destination: 'COMMERCIAL', available: true }, '']);
  });

  it('a busca não exibe indisponíveis nem didáticos: só o que o backend devolve filtrado', () => {
    const { fixture, root } = setup(() => undefined);
    submitSearch(fixture, root, 'Sapiens');
    expect(root.querySelectorAll('article').length).toBe(1);
    expect(root.textContent).not.toContain('Indisponível para venda');
    expect(root.textContent).not.toContain('Didático');
  });

  it('mostra destinação, disponibilidade, preço e estoque reais do exemplar comercial', () => {
    const { fixture, root } = setup(() => undefined);
    pickClient(fixture, root);
    const card = root.querySelector('article')!;
    expect(card.textContent).toContain('Sapiens');
    expect(card.textContent?.replace(/\s+/g, ' ')).toContain('Comercial • Disponível para venda');
    expect(card.textContent).toContain('Exemplar C-007');
    expect(card.textContent).toContain('3 exemplar(es) comercial(is) livre(s)');
    expect(card.textContent?.replace(/ /g, ' ')).toContain('R$ 38,90');
    expect(root.querySelector('input[type="number"]')).toBeNull();
    expect(button(root, 'Registrar venda').disabled).toBeFalse();
  });

  it('exige o cliente: sem seleção o botão fica desligado, avisa e nenhuma venda é enviada', () => {
    const { fixture, root, service } = setup(() => undefined);
    expect(root.textContent).toContain('Selecione o cliente para registrar a venda.');
    expect(button(root, 'Registrar venda').disabled).toBeTrue();
    button(root, 'Registrar venda').click();
    fixture.detectChanges();
    expect(root.querySelector('dialog')).toBeNull();
    expect(service.registerSale).not.toHaveBeenCalled();
    pickClient(fixture, root);
    expect(root.textContent).toContain('Maria Silva · maria@x.dev');
    expect(root.textContent).not.toContain('Selecione o cliente para registrar a venda.');
    click(fixture, button(root, 'Trocar cliente'));
    expect(button(root, 'Registrar venda').disabled).toBeTrue();
  });

  it('filtra clientes pelo termo e não deixa escolher cadastro inativo', () => {
    const { fixture, root, service } = setup((s) =>
      s.searchClients.and.returnValue(of([client({ is_active: false, eligible: false }), client({ id: 4, name: 'Bia Penal', is_penalized: true })])));
    const input = root.querySelector('#sale-client') as HTMLInputElement;
    input.value = 'bia';
    input.dispatchEvent(new Event('input'));
    input.closest('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(service.searchClients).toHaveBeenCalledWith('bia');
    const rows = Array.from(root.querySelectorAll('app-client-picker .result'));
    expect((rows[0].querySelector('button') as HTMLButtonElement).disabled).toBeTrue();
    expect(rows[0].textContent).toContain('cadastro inativo');
    expect(rows[1].textContent).toContain('penalizado (não bloqueia a venda)');
    click(fixture, rows[1].querySelector('button') as HTMLElement);
    expect(root.textContent).toContain('a penalidade não bloqueia a venda');
    expect(button(root, 'Registrar venda').disabled).toBeFalse();
  });


  it('não permite registrar sem preço cadastrado', () => {
    const { fixture, root, service } = setup((s) => s.listCopies.and.returnValue(of([copy({ sale_price: null })])));
    pickClient(fixture, root);
    expect(root.textContent).toContain('Sem preço de venda cadastrado');
    expect(button(root, 'Registrar venda').disabled).toBeTrue();
    expect(service.registerSale).not.toHaveBeenCalled();
  });

  it('mostra carregamento, vazio e erro da lista de forma distinta', () => {
    const waiting = new Subject<StaffCopyLookup[]>();
    const { fixture, root, service } = setup((s) => s.listCopies.and.returnValue(waiting));
    expect(root.textContent).toContain('Carregando exemplares');
    waiting.next([]);
    fixture.detectChanges();
    expect(root.querySelector('.empty')?.textContent).toContain('Nenhum exemplar comercial disponível para venda no momento.');
    service.listCopies.and.returnValue(of([]));
    submitSearch(fixture, root, 'X-1');
    expect(root.querySelector('.empty')?.textContent).toContain('Nenhum exemplar disponível para “X-1”');
    service.listCopies.and.returnValue(throwError(() => ({ detail: 'Falha ao consultar.' })));
    submitSearch(fixture, root, 'X-2');
    expect(root.querySelector('app-alert')?.textContent).toContain('Falha ao consultar.');
    expect(root.querySelector('.empty')).toBeNull();
  });

  it('avisa quando o limite de resultados é atingido', () => {
    const many = Array.from({ length: 20 }, (_, i) => copy({ id: i + 1, barcode: `C-${i}` }));
    const { root } = setup((s) => s.listCopies.and.returnValue(of(many)));
    expect(root.textContent).toContain('Mostrando os primeiros 20');
  });

  it('pede confirmação antes do POST com o cliente, informa a confirmação no ato e cancelar não envia', () => {
    const { fixture, root, service } = setup(() => undefined);
    pickClient(fixture, root);
    click(fixture, button(root, 'Registrar venda'));
    expect(dialog(root)?.textContent).toContain('Registrar venda?');
    expect(dialog(root)?.textContent).toContain('Cliente: Maria Silva · maria@x.dev');
    expect(dialog(root)?.textContent).toContain('A venda será confirmada no ato e o exemplar ficará vendido.');
    expect(dialog(root)?.textContent).not.toContain('pendente');
    click(fixture, button(root, 'Cancelar'));
    expect(dialog(root)).toBeNull();
    expect(service.registerSale).not.toHaveBeenCalled();
  });

  it('envia o cliente, não envia preço, bloqueia duplo envio e só anuncia a venda registrada após o 2xx', () => {
    const response = new Subject<SaleRegistration>();
    const { fixture, root, service } = setup((s) => s.registerSale.and.returnValue(response));
    pickClient(fixture, root);
    click(fixture, button(root, 'Registrar venda'));
    const submit = submitButton(root);
    click(fixture, submit);
    click(fixture, submit);
    expect(service.registerSale).toHaveBeenCalledOnceWith(3, 7);
    expect(submit.disabled).toBeTrue();
    expect(snackbarMessage()).toBe('');
    service.listCopies.and.returnValue(of([]));
    response.next(confirmed);
    response.complete();
    fixture.detectChanges();
    expect(dialog(root)).toBeNull();
    const feedback = snackbarMessage() ?? '';
    expect(feedback).toContain('Venda registrada para Maria Silva');
    expect(feedback).toContain('C-007 vendido');
    expect(feedback).toContain('38,90');
    expect(feedback).toContain('venda nº 12');
    expect(receiptGet()).toHaveBeenCalledOnceWith('sale', 12);
    expect(root.querySelector('app-receipt')).not.toBeNull();
    expect(feedback).not.toMatch(/pendente/i);
    expect(service.listCopies).toHaveBeenCalledTimes(2);
    expect(root.querySelector('article button')).toBeNull();
    expect(root.textContent).toContain('Selecione o cliente para registrar a venda.');
  });

  it('mostra o erro de domínio sem sucesso e refaz a lista', () => {
    const { fixture, root, service } = setup((s) =>
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Um ou mais exemplares não estão disponíveis para venda.', status: 409 }))));
    pickClient(fixture, root);
    click(fixture, button(root, 'Registrar venda'));
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('não estão disponíveis para venda');
    expect(snackbarMessage()).not.toContain('Venda registrada');
    expect(service.listCopies).toHaveBeenCalledTimes(2);
  });

  it('mostra o erro de cliente inativo devolvido pelo backend, sem sucesso', () => {
    const { fixture, root } = setup((s) =>
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Cliente inativo.', code: 'client_inactive', status: 403 }))));
    pickClient(fixture, root);
    click(fixture, button(root, 'Registrar venda'));
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('Cliente inativo.');
    expect(snackbarMessage()).not.toContain('Venda registrada');
  });

  for (const status of [0, 503]) {
    it(`falha de persistência/rede (${status}) mostra "Não foi possível salvar" sem snackbar nem reenvio`, () => {
      const { fixture, root, service } = setup((s) =>
        s.registerSale.and.returnValue(throwError(() => ({ status, detail: 'Tivemos um problema no servidor.' }))));
      pickClient(fixture, root);
      click(fixture, button(root, 'Registrar venda'));
      click(fixture, submitButton(root));
      const card = root.querySelector('app-save-failure')!;
      expect(card.textContent).toContain('Não foi possível salvar');
      expect(card.textContent).toContain('Atualize a consulta antes de repetir a operação para evitar registros duplicados.');
      expect(snackbarMessage()).toBe('');
      expect(root.textContent).not.toContain('Venda registrada');
      expect(service.registerSale).toHaveBeenCalledTimes(1);
      expect(service.listCopies).toHaveBeenCalledTimes(2);
      click(fixture, button(root, 'Atualizar consulta'));
      expect(service.listCopies).toHaveBeenCalledTimes(3);
      expect(service.registerSale).toHaveBeenCalledTimes(1);
      click(fixture, button(root, 'Voltar'));
      expect(root.querySelector('app-save-failure')).toBeNull();
    });
  }

  it('exibe o erro de exemplar sem preço devolvido pelo backend, sem sucesso', () => {
    const { fixture, root } = setup((s) =>
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Este exemplar comercial não tem preço de venda cadastrado e não pode ser vendido.', code: 'copy_without_price', status: 409 }))));
    pickClient(fixture, root);
    click(fixture, button(root, 'Registrar venda'));
    click(fixture, submitButton(root));
    expect(snackbarMessage()).toContain('não tem preço de venda cadastrado');
    expect(snackbarMessage()).not.toContain('Venda registrada');
  });

  it('exibe o erro de domínio de exemplar didático devolvido pelo backend', () => {
    const { fixture, root } = setup((s) =>
      s.registerSale.and.returnValue(throwError(() => ({ detail: 'Exemplares didáticos não podem ser vendidos.', status: 409 }))));
    pickClient(fixture, root);
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
