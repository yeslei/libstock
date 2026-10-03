import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';

import { RoleCode } from '../../core/models/user.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { BookService } from '../books/services/book.service';
import { CounterCatalogBookComponent } from './counter-catalog-book.component';
import { CounterService, StaffCatalogBookDetail, StaffCatalogCopy } from './counter.service';

const copy = (over: Partial<StaffCatalogCopy> = {}): StaffCatalogCopy => ({
  id: 1, barcode: '00101', destination: 'DIDACTIC', status: 'AVAILABLE', condition: null, sale_price: null,
  is_active: true, free: true, allocated_for_purchase: false, ...over,
});

const detail = (over: Partial<StaffCatalogBookDetail> = {}): StaffCatalogBookDetail => ({
  id: 7, title: 'Dom Casmurro', author: 'Machado de Assis', isbn: '9780000000002', genre: 'Romance', is_active: true,
  total_copies: 4, didactic_copies: 2, commercial_copies: 2,
  copies: [
    copy(),
    copy({ id: 2, barcode: '00102', status: 'BORROWED', free: false }),
    copy({ id: 3, barcode: '00103', destination: 'COMMERCIAL', sale_price: '39.90' }),
    copy({ id: 4, barcode: '00104', destination: 'COMMERCIAL', free: false, allocated_for_purchase: true }),
  ],
  ...over,
});

function setup(book$: Observable<StaffCatalogBookDetail>, roles: RoleCode[] = ['SELLER']) {
  const counter = jasmine.createSpyObj<CounterService>('CounterService', ['getCatalogBook']);
  counter.getCatalogBook.and.returnValue(book$);
  const books = jasmine.createSpyObj<BookService>('BookService', ['update']);
  TestBed.configureTestingModule({
    imports: [CounterCatalogBookComponent],
    providers: [
      provideRouter([]),
      { provide: CounterService, useValue: counter },
      { provide: BookService, useValue: books },
      { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: '7' })) } },
    ],
  });
  TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: roles, created_at: '' });
  const fixture = TestBed.createComponent(CounterCatalogBookComponent);
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  const button = (label: string) =>
    Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label) as HTMLButtonElement | undefined;
  return { fixture, counter, books, root, button };
}

type Ctx = ReturnType<typeof setup>;

function edit(ctx: Ctx, value: string) {
  ctx.button('Editar obra')!.click();
  ctx.fixture.detectChanges();
  const input = ctx.root.querySelector('#book-genre') as HTMLInputElement;
  input.value = value;
  input.dispatchEvent(new Event('input'));
  ctx.fixture.detectChanges();
}

function confirmDialog(ctx: Ctx) {
  (ctx.root.querySelector('.confirm__submit') as HTMLButtonElement).click();
  ctx.fixture.detectChanges();
}

describe('Balcão: detalhes da obra', () => {
  it('mostra dados da obra e exemplares reais, sem ações de escrita para o vendedor', () => {
    const { root, counter, button } = setup(of(detail()));
    expect(counter.getCatalogBook).toHaveBeenCalledWith(7);
    expect(root.querySelector('h1')?.textContent).toBe('Dom Casmurro');
    expect(root.textContent).toContain('Machado de Assis • ISBN 9780000000002');
    expect(root.textContent).toContain('Categoria literária: Romance');
    expect(root.textContent).toContain('2 para empréstimo · 2 para venda');
    expect(root.textContent).toContain('Status da obra: Ativa');
    expect(root.textContent).toContain('Quantidade total: 4 exemplares');
    const rows = Array.from(root.querySelectorAll('tbody tr')).map((r) =>
      Array.from(r.querySelectorAll('td')).map((td) => td.textContent?.trim()));
    expect(rows).toEqual([
      ['00101', 'Empréstimo', 'Disponível'],
      ['00102', 'Empréstimo', 'Emprestado'],
      ['00103', 'Venda', 'Disponível'],
      ['00104', 'Venda', 'Reservado para venda'],
    ]);
    expect(button('Editar obra')).toBeUndefined();
    expect(button('Inativar obra')).toBeUndefined();
    expect(root.querySelector('input')).toBeNull();
    expect(root.textContent).not.toContain('Excluir exemplar');
    expect(root.textContent).not.toContain('Novo exemplar');
  });

  it('oferece Novo exemplar apenas a papéis autorizados e a obras ativas', () => {
    const admin = setup(of(detail()), ['ADMINISTRATOR']);
    const link = Array.from(admin.root.querySelectorAll('a')).find((a) => a.textContent?.trim() === 'Novo exemplar');
    expect(link?.getAttribute('href')).toBe('/balcao/acervo/7/exemplares/novo');
    TestBed.resetTestingModule();
    const inactive = setup(of(detail({ is_active: false })), ['ADMINISTRATOR']);
    expect(inactive.root.textContent).not.toContain('Novo exemplar');
  });

  it('mostra carregamento, depois erro de domínio com nova tentativa', () => {
    const pending = new Subject<StaffCatalogBookDetail>();
    const { fixture, root, counter, button } = setup(pending);
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Carregando obra');
    pending.error({ detail: 'Obra não encontrada.' });
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Obra não encontrada.');
    counter.getCatalogBook.and.returnValue(of(detail()));
    button('Tentar novamente')!.click();
    fixture.detectChanges();
    expect(root.querySelector('h1')?.textContent).toBe('Dom Casmurro');
  });

  it('informa obra sem exemplares e o singular de um exemplar', () => {
    const { root } = setup(of(detail({ copies: [], total_copies: 1, genre: null })));
    expect(root.textContent).toContain('Nenhum exemplar cadastrado');
    expect(root.textContent).toContain('Quantidade total: 1 exemplar');
    expect(root.textContent).toContain('Categoria literária: —');
  });

  it('exibe inativo e vendido conforme o backend', () => {
    const { root } = setup(of(detail({
      copies: [copy({ is_active: false, status: 'INACTIVE', free: false }), copy({ id: 2, status: 'SOLD', free: false })],
    })));
    expect(Array.from(root.querySelectorAll('tbody .pill')).map((p) => p.textContent)).toEqual(['Inativo', 'Vendido']);
  });

  describe('papéis autorizados a editar', () => {
    const admin: RoleCode[] = ['ADMINISTRATOR'];

    it('só edita depois de abrir "Editar obra"', () => {
      const { fixture, root, button } = setup(of(detail()), admin);
      expect(root.querySelector('input')).toBeNull();
      button('Editar obra')!.click();
      fixture.detectChanges();
      expect((root.querySelector('#book-genre') as HTMLInputElement).value).toBe('Romance');
      expect(button('Salvar alteração')!.disabled).toBeTrue();
      expect(root.textContent).toContain('A destinação é definida em cada exemplar');
    });

    it('pede confirmação, bloqueia duplo envio e só confirma sucesso após 2xx, recarregando', () => {
      const ctx = setup(of(detail()), admin);
      const patch = new Subject<unknown>();
      ctx.books.update.and.returnValue(patch as never);
      edit(ctx, ' Ficção ');
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      expect(ctx.root.querySelector('dialog')?.textContent).toContain('Romance → Ficção');

      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).toHaveBeenCalledTimes(1);
      expect(ctx.books.update).toHaveBeenCalledWith(7, { genre: 'Ficção' });
      expect(ctx.root.textContent).not.toContain('atualizada');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(1);

      ctx.counter.getCatalogBook.and.returnValue(of(detail({ genre: 'Ficção' })));
      patch.next({});
      patch.complete();
      ctx.fixture.detectChanges();
      expect(ctx.root.textContent).toContain('Categoria de “Dom Casmurro” atualizada.');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(ctx.root.textContent).toContain('Categoria literária: Ficção');
    });

    it('cancelar não altera nada', () => {
      const ctx = setup(of(detail()), admin);
      edit(ctx, 'Ficção');
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Cancelar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      expect(ctx.root.querySelector('dialog')).toBeNull();
    });

    it('envia categoria vazia como nula', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(of({}) as never);
      edit(ctx, '   ');
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(ctx.books.update).toHaveBeenCalledWith(7, { genre: null });
    });

    it('bloqueia categoria acima de 100 caracteres', () => {
      const ctx = setup(of(detail()), admin);
      edit(ctx, 'x'.repeat(101));
      expect(ctx.root.textContent).toContain('A categoria aceita até 100 caracteres.');
      expect(ctx.button('Salvar alteração')!.disabled).toBeTrue();
    });

    it('mostra erro de domínio sem anunciar sucesso e recarrega', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(throwError(() => ({ status: 409, detail: 'Obra não pode ser alterada.' })));
      edit(ctx, 'Ficção');
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[role="alert"]')?.textContent).toContain('Obra não pode ser alterada.');
      expect(ctx.root.textContent).not.toContain('atualizada');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });

    it('inativa a obra somente após confirmação e não oferece reativação', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(of({}) as never);
      ctx.button('Editar obra')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      ctx.counter.getCatalogBook.and.returnValue(of(detail({ is_active: false })));
      confirmDialog(ctx);
      expect(ctx.books.update).toHaveBeenCalledOnceWith(7, { is_active: false });
      expect(ctx.root.textContent).toContain('Obra “Dom Casmurro” inativada.');
      expect(ctx.root.textContent).toContain('Status da obra: Inativa');
      expect(ctx.button('Inativar obra')).toBeUndefined();
      expect(ctx.root.textContent).toContain('A reativação ainda não está disponível.');
    });

    it('oferece edição também a STOCK_KEEPER, papel autorizado pelo backend', () => {
      const keeper = setup(of(detail()), ['STOCK_KEEPER']);
      expect(keeper.button('Editar obra')).toBeDefined();
    });
  });
});
