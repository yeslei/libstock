import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { routes } from '../../app.routes';
import { TokenStoreService } from '../../core/services/token-store.service';
import { ReceiptPageComponent } from './receipt-page.component';
import { ReceiptComponent } from './receipt.component';
import { LoanReceipt, ReceiptKind, ReceiptService, ReturnReceipt, SaleReceipt, receiptPath } from './receipt.service';
import { toReceiptView } from './receipt-view';

const book = { title: 'Dom Casmurro', author: 'Machado de Assis', isbn: null };
const loan: LoanReceipt = {
  number: 41,
  client: { id: 3, name: 'Maria Silva', code: 'MAT-9' },
  employee: { id: 2, name: 'Beto Balcão', code: 'F-1' },
  book,
  copy_id: 9,
  copy_barcode: '00101',
  loan_date: '2026-10-03T15:30:00-03:00',
  due_date: '2026-11-03T15:30:00-03:00',
};
const returned: ReturnReceipt = { ...loan, returned_at: '2026-11-06T10:05:00-03:00', days_late: 3 };
const sale: SaleReceipt = {
  number: 8,
  client: null,
  employee: loan.employee,
  sale_date: '2026-10-03T16:00:00-03:00',
  items: [
    { copy_id: 1, copy_barcode: 'A-1', book, unit_price: '37.50' },
    { copy_id: 2, copy_barcode: 'A-2', book: { ...book, title: 'Quincas Borba' }, unit_price: '12.25' },
  ],
  total_amount: '49.75',
};

function setup(kind: ReceiptKind, id: number | string, extra: { closable?: boolean } = {}) {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  const fixture = TestBed.createComponent(ReceiptComponent);
  fixture.componentRef.setInput('kind', kind);
  fixture.componentRef.setInput('id', id);
  if (extra.closable) fixture.componentRef.setInput('closable', true);
  fixture.detectChanges();
  return { fixture, http: TestBed.inject(HttpTestingController), root: fixture.nativeElement as HTMLElement };
}

async function settle(fixture: ComponentFixture<unknown>) {
  await fixture.whenStable();
  fixture.detectChanges();
}

const text = (root: HTMLElement) => root.textContent?.replace(/\s+/g, ' ') ?? '';

describe('Comprovante', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('mostra o estado de carregamento antes da resposta e consulta o endpoint do empréstimo', async () => {
    const { fixture, http, root } = setup('loan', 41);
    await settle(fixture);
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Carregando comprovante');
    expect(root.querySelector('.receipt')).toBeNull();
    const request = http.expectOne('/api/v1/receipts/loans/41');
    expect(request.request.method).toBe('GET');
    request.flush(loan);
  });

  it('exibe os dados persistidos do empréstimo', async () => {
    const { fixture, http, root } = setup('loan', '41');
    await settle(fixture);
    http.expectOne('/api/v1/receipts/loans/41').flush(loan);
    await settle(fixture);
    const content = text(root);
    expect(root.querySelector('h2')?.textContent).toBe('Comprovante de empréstimo');
    for (const expected of ['Empréstimo nº 41', 'Maria Silva (MAT-9)', 'Dom Casmurro — Machado de Assis', '00101', '03/10/2026 15:30', '03/11/2026', 'Beto Balcão (F-1)']) {
      expect(content).toContain(expected);
    }
    expect(content).not.toContain('atraso');
  });

  it('exibe a devolução com a data gravada e o atraso informado pelo backend', async () => {
    const { fixture, http, root } = setup('return', 41);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/returns/41').flush(returned);
    await settle(fixture);
    const content = text(root);
    expect(root.querySelector('h2')?.textContent).toBe('Comprovante de devolução');
    expect(content).toContain('06/11/2026 10:05');
    expect(content).toContain('3 dias de atraso');
    expect(content).not.toMatch(/multa|R\$/i);
  });

  it('informa devolução no prazo quando não há atraso', async () => {
    const { fixture, http, root } = setup('return', 41);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/returns/41').flush({ ...returned, days_late: 0 });
    await settle(fixture);
    expect(text(root)).toContain('Devolvido no prazo');
  });

  it('exibe itens, preços e total da venda, inclusive sem cliente', async () => {
    const { fixture, http, root } = setup('sale', 8);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/sales/8').flush(sale);
    await settle(fixture);
    const content = text(root);
    expect(content).toContain('Venda nº 8');
    expect(content).toContain('Venda sem cliente identificado');
    expect(root.querySelectorAll('tbody tr').length).toBe(2);
    expect(content).toContain('Quincas Borba');
    expect(content).toMatch(/R\$\s?37,50/);
    expect(content).toMatch(/Total\s*R\$\s*49,75/);
  });

  it('imprime com window.print ao acionar o botão', async () => {
    const { fixture, http, root } = setup('loan', 41);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/loans/41').flush(loan);
    await settle(fixture);
    const print = spyOn(window, 'print');
    const button = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Imprimir comprovante');
    expect(button).toBeTruthy();
    button!.click();
    expect(print).toHaveBeenCalledTimes(1);
  });

  it('mostra o erro do backend, permite tentar de novo e não imprime', async () => {
    const { fixture, http, root } = setup('loan', 41);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/loans/41').flush({ detail: 'x' }, { status: 404, statusText: 'Not Found' });
    await settle(fixture);
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar o comprovante');
    expect(root.querySelector('.receipt')).toBeNull();
    expect(text(root)).not.toContain('Imprimir comprovante');
    (root.querySelector('.receipt-btn') as HTMLButtonElement).click();
    await settle(fixture);
    http.expectOne('/api/v1/receipts/loans/41').flush(loan);
    await settle(fixture);
    expect(root.querySelector('.receipt')).not.toBeNull();
  });

  it('fecha o comprovante quando exibido dentro de outra tela', async () => {
    const { fixture, http, root } = setup('loan', 41, { closable: true });
    let closed = 0;
    fixture.componentInstance.closed.subscribe(() => closed++);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/loans/41').flush(loan);
    await settle(fixture);
    const button = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Fechar comprovante');
    button!.click();
    expect(closed).toBe(1);
  });

  it('o articulo é nomeado pelo título para leitores de tela', async () => {
    const { fixture, http, root } = setup('loan', 41);
    await settle(fixture);
    http.expectOne('/api/v1/receipts/loans/41').flush(loan);
    await settle(fixture);
    const article = root.querySelector('article')!;
    expect(root.querySelector(`#${article.getAttribute('aria-labelledby')}`)?.textContent).toBe('Comprovante de empréstimo');
    expect(root.querySelector('dl')).not.toBeNull();
  });
});

describe('Comprovante: modelo de exibição e rotas', () => {
  it('formata a venda sem inventar valores', () => {
    const view = toReceiptView('sale', sale);
    expect(view.total).toContain('49,75');
    expect(view.items.map((item) => item.detail)).toEqual(['Exemplar A-1', 'Exemplar A-2']);
  });

  it('gera o caminho de cada comprovante', () => {
    expect(receiptPath('loan', 5)).toBe('/comprovantes/emprestimo/5');
    expect(receiptPath('return', 5)).toBe('/comprovantes/devolucao/5');
    expect(receiptPath('sale', 5)).toBe('/comprovantes/venda/5');
  });

  it('consulta os três endpoints somente leitura', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const service = TestBed.inject(ReceiptService);
    const http = TestBed.inject(HttpTestingController);
    service.get('loan', 1).subscribe();
    service.get('return', 2).subscribe();
    service.get('sale', 3).subscribe();
    for (const url of ['/api/v1/receipts/loans/1', '/api/v1/receipts/returns/2', '/api/v1/receipts/sales/3']) {
      const request = http.expectOne(url);
      expect(request.request.method).toBe('GET');
      request.flush({});
    }
    http.verify();
  });

  it('declara as rotas dedicadas com guard de sessão e papéis de funcionário ou cliente', () => {
    for (const [segment, kind] of [['emprestimo', 'loan'], ['devolucao', 'return'], ['venda', 'sale']]) {
      const route = routes.find((r) => r.path === `comprovantes/${segment}/:id`);
      expect(route).toBeTruthy();
      expect(route!.canActivate?.length).toBe(2);
      expect(route!.data).toEqual({ roles: ['USER', 'SELLER', 'ADMINISTRATOR'], receipt: kind });
    }
  });

  it('a página do comprovante volta ao balcão para funcionário e a Meus empréstimos para cliente', async () => {
    for (const [role, label] of [['SELLER', 'Voltar ao balcão'], ['USER', 'Meus empréstimos']]) {
      TestBed.resetTestingModule();
      TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
      TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'U', email: 'u@x.dev', role_codes: [role] } as never);
      const fixture = TestBed.createComponent(ReceiptPageComponent);
      fixture.componentRef.setInput('id', '7');
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('a')?.textContent).toContain(label);
      TestBed.inject(HttpTestingController).expectOne((request) => request.url.startsWith('/api/v1/receipts/'));
    }
  });
});
