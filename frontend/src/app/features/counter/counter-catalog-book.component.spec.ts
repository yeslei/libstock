import {
  snackbarMessage,
  snackbarVariant,
} from '../../shared/components/snackbar/snackbar.testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';

import { RoleCode } from '../../core/models/user.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { BookService } from '../books/services/book.service';
import { CopyService } from '../copies/services/copy.service';
import { Genre } from '../catalog/models/catalog.model';
import { CatalogService } from '../catalog/services/catalog.service';
import { CounterCatalogBookComponent } from './counter-catalog-book.component';
import { CounterService, StaffCatalogBookDetail, StaffCatalogCopy } from './counter.service';

const copy = (over: Partial<StaffCatalogCopy> = {}): StaffCatalogCopy => ({
  id: 1,
  barcode: '00101',
  destination: 'DIDACTIC',
  status: 'AVAILABLE',
  condition: null,
  sale_price: null,
  is_active: true,
  free: true,
  allocated_for_purchase: false,
  ...over,
});

const detail = (over: Partial<StaffCatalogBookDetail> = {}): StaffCatalogBookDetail => ({
  id: 7,
  title: 'Dom Casmurro',
  author: 'Machado de Assis',
  isbn: '9780000000002',
  genre: 'Romance',
  genres: [{ id: 7, name: 'Romance', slug: 'romance' }],
  is_active: true,
  total_copies: 4,
  didactic_copies: 2,
  commercial_copies: 2,
  copies: [
    copy(),
    copy({ id: 2, barcode: '00102', status: 'BORROWED', free: false }),
    copy({ id: 3, barcode: '00103', destination: 'COMMERCIAL', sale_price: '39.90' }),
    copy({
      id: 4,
      barcode: '00104',
      destination: 'COMMERCIAL',
      free: false,
      allocated_for_purchase: true,
    }),
  ],
  ...over,
});

const CATALOG_GENRES: Genre[] = [
  { id: 1, name: 'Ficção', slug: 'ficcao' },
  { id: 4, name: 'Fantasia', slug: 'fantasia' },
  { id: 7, name: 'Romance', slug: 'romance' },
];

function setup(book$: Observable<StaffCatalogBookDetail>, roles: RoleCode[] = ['SELLER']) {
  const counter = jasmine.createSpyObj<CounterService>('CounterService', ['getCatalogBook']);
  counter.getCatalogBook.and.returnValue(book$);
  const books = jasmine.createSpyObj<BookService>('BookService', ['update']);
  const copies = jasmine.createSpyObj<CopyService>('CopyService', ['delete', 'update']);
  const catalog = jasmine.createSpyObj<CatalogService>('CatalogService', ['getAllGenres']);
  catalog.getAllGenres.and.returnValue(of(CATALOG_GENRES));
  TestBed.configureTestingModule({
    imports: [CounterCatalogBookComponent],
    providers: [
      provideRouter([]),
      { provide: CounterService, useValue: counter },
      { provide: BookService, useValue: books },
      { provide: CopyService, useValue: copies },
      { provide: CatalogService, useValue: catalog },
      { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: '7' })) } },
    ],
  });
  TestBed.inject(TokenStoreService).setSession('t', {
    id: 1,
    name: 'F',
    email: 'f@x.dev',
    role_codes: roles,
    created_at: '',
  });
  const fixture = TestBed.createComponent(CounterCatalogBookComponent);
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  const button = (label: string) =>
    Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label) as
      | HTMLButtonElement
      | undefined;
  return { fixture, counter, books, copies, catalog, root, button };
}

type Ctx = ReturnType<typeof setup>;

/** Abre "Editar obra" e deixa marcadas exatamente as categorias com os nomes dados. */
function edit(ctx: Ctx, names: string[]) {
  ctx.button('Editar categorias')!.click();
  ctx.fixture.detectChanges();
  for (const genre of CATALOG_GENRES) {
    const box = ctx.root.querySelector(`#book-genre-${genre.id}`) as HTMLInputElement;
    if (box.checked !== names.includes(genre.name)) box.click();
    ctx.fixture.detectChanges();
  }
}

function confirmDialog(ctx: Ctx) {
  (ctx.root.querySelector('.confirm__submit') as HTMLButtonElement).click();
  ctx.fixture.detectChanges();
}

function selectCopy(ctx: Ctx, row = 0): void {
  (ctx.root.querySelectorAll('tbody tr .copy-code')[row] as HTMLButtonElement).click();
  ctx.fixture.detectChanges();
}

function deleteButton(ctx: Ctx, row = 0): HTMLButtonElement {
  selectCopy(ctx, row);
  return ctx.root.querySelector('[data-copy-management] .btn--danger') as HTMLButtonElement;
}

describe('Balcão: detalhes da obra', () => {
  it('mostra dados da obra e exemplares reais, sem ações de escrita para quem não administra o acervo', () => {
    const { root, counter, button } = setup(of(detail()), ['USER']);
    expect(counter.getCatalogBook).toHaveBeenCalledWith(7);
    expect(root.querySelector('h1')?.textContent).toBe('Dom Casmurro');
    expect(root.querySelector('.operation-links')).toBeNull();
    expect(root.textContent).toContain('Machado de Assis • ISBN 9780000000002');
    expect(root.textContent).toContain('Categoria literária: Romance');
    expect(root.textContent).toContain('Status da obra: Ativa');
    const rows = Array.from(root.querySelectorAll('tbody tr')).map((r) =>
      Array.from(r.querySelectorAll('td')).map((td) => td.textContent?.trim()),
    );
    expect(rows).toEqual([
      ['00101', 'Empréstimo', 'Não informada', '—', 'Disponível'],
      ['00102', 'Empréstimo', 'Não informada', '—', 'Emprestado'],
      ['00103', 'Venda', 'Não informada', 'R$\u00a039,90', 'Disponível'],
      ['00104', 'Venda', 'Não informada', '—', 'Reservado para venda'],
    ]);
    expect(button('Editar categorias')).toBeUndefined();
    expect(button('Inativar obra')).toBeUndefined();
    expect(root.querySelector('input')).toBeNull();
    expect(root.textContent).not.toContain('Excluir exemplar');
    expect(root.textContent).not.toContain('Adicionar exemplares');
    expect(root.textContent).not.toContain('Editar exemplar');
  });

  it('oferece ao vendedor as ações de acervo: editar obra, novo exemplar, editar e excluir exemplar', () => {
    const { root, button } = setup(of(detail()), ['SELLER']);
    expect(button('Editar categorias')).toBeDefined();
    expect(
      Array.from(root.querySelectorAll('a')).some(
        (a) => a.textContent?.trim() === 'Adicionar exemplares',
      ),
    ).toBeTrue();
    expect(root.querySelector('thead')?.textContent).not.toContain('Ações');
    expect(root.querySelectorAll('tbody tr .copy-code').length).toBe(4);
    expect(root.querySelector('[data-copy-management]')).toBeNull();
  });

  it('estoquista gerencia o acervo sem acesso às operações de circulação', () => {
    const { root, button } = setup(of(detail({ is_active: true })), ['STOCK_KEEPER']);
    const link = Array.from(root.querySelectorAll('a')).find(
      (a) => a.textContent?.trim() === 'Adicionar exemplares',
    );
    expect(link?.getAttribute('href')).toBe('/balcao/acervo/7/exemplares/lote');
    for (const label of ['Editar categorias'])
      expect(button(label)).withContext(label).toBeDefined();
    expect(root.querySelector('.operation-links')).toBeNull();
    expect(root.querySelector('thead')?.textContent).not.toContain('Ações');
    expect(root.querySelectorAll('tbody tr .copy-code').length).toBe(4);
    expect(root.querySelector('[data-copy-management]')).toBeNull();
    expect(root.querySelectorAll('tbody tr').length).toBe(4);
  });

  it('oferece Novo exemplar apenas a papéis autorizados e a obras ativas', () => {
    const admin = setup(of(detail()), ['ADMINISTRATOR']);
    const link = Array.from(admin.root.querySelectorAll('a')).find(
      (a) => a.textContent?.trim() === 'Adicionar exemplares',
    );
    expect(link?.getAttribute('href')).toBe('/balcao/acervo/7/exemplares/lote');
    TestBed.resetTestingModule();
    const user = setup(of(detail()), ['USER']);
    expect(user.root.textContent).not.toContain('Adicionar exemplares');
    TestBed.resetTestingModule();
    const inactive = setup(of(detail({ is_active: false })), ['ADMINISTRATOR']);
    expect(inactive.root.textContent).not.toContain('Adicionar exemplares');
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

  it('informa obra sem exemplares e sem categoria', () => {
    const { root } = setup(of(detail({ copies: [], total_copies: 1, genre: null, genres: [] })));
    expect(root.textContent).toContain('Nenhum exemplar cadastrado');
    expect(root.textContent).toContain('Categoria literária: —');
  });

  it('exibe inativo e vendido conforme o backend', () => {
    const { root } = setup(
      of(
        detail({
          copies: [
            copy({ is_active: false, status: 'INACTIVE', free: false }),
            copy({ id: 2, status: 'SOLD', free: false }),
          ],
        }),
      ),
    );
    expect(Array.from(root.querySelectorAll('tbody .pill')).map((p) => p.textContent)).toEqual([
      'Inativo',
      'Vendido',
    ]);
  });

  describe('papéis autorizados a editar', () => {
    const admin: RoleCode[] = ['ADMINISTRATOR'];

    it('só edita depois de abrir "Editar obra"', () => {
      const { fixture, root, button } = setup(of(detail()), admin);
      expect(root.querySelector('input')).toBeNull();
      button('Editar categorias')!.click();
      fixture.detectChanges();
      const boxes = Array.from(root.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'));
      expect(boxes.map((box) => [box.id, box.checked])).toEqual([
        ['book-genre-1', false],
        ['book-genre-4', false],
        ['book-genre-7', true],
      ]);
      expect(button('Salvar alteração')!.disabled).toBeTrue();
      expect(root.querySelector('.card h2')?.textContent).not.toBe('Editar obra');
    });

    it('pede confirmação, bloqueia duplo envio e só confirma sucesso após 2xx, recarregando', () => {
      const ctx = setup(of(detail()), admin);
      const patch = new Subject<unknown>();
      ctx.books.update.and.returnValue(patch as never);
      edit(ctx, ['Ficção']);
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      expect(ctx.root.querySelector('dialog')?.textContent).toContain('Romance → Ficção');

      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).toHaveBeenCalledTimes(1);
      expect(ctx.books.update).toHaveBeenCalledWith(7, { genre_ids: [1] });
      expect(snackbarMessage()).not.toContain('atualizadas');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(1);

      ctx.counter.getCatalogBook.and.returnValue(
        of(detail({ genre: 'Ficção', genres: [{ id: 1, name: 'Ficção', slug: 'ficcao' }] })),
      );
      patch.next({});
      patch.complete();
      ctx.fixture.detectChanges();
      expect(snackbarMessage()).toContain('Categorias de “Dom Casmurro” atualizadas.');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(ctx.root.textContent).toContain('Categoria literária: Ficção');
    });

    it('cancelar não altera nada', () => {
      const ctx = setup(of(detail()), admin);
      edit(ctx, ['Ficção']);
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Cancelar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      expect(ctx.root.querySelector('dialog')).toBeNull();
    });

    it('remover todas as categorias envia lista vazia', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(of({}) as never);
      edit(ctx, []);
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('dialog')?.textContent).toContain('Romance → sem categoria');
      confirmDialog(ctx);
      expect(ctx.books.update).toHaveBeenCalledWith(7, { genre_ids: [] });
    });

    it('permite escolher várias categorias do catálogo (seleção múltipla)', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(of({}) as never);
      edit(ctx, ['Romance', 'Fantasia']);
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(ctx.books.update).toHaveBeenCalledWith(7, { genre_ids: [7, 4] });
    });

    it('sem mudança de seleção o botão fica desabilitado', () => {
      const ctx = setup(of(detail()), admin);
      edit(ctx, ['Romance']);
      expect(ctx.button('Salvar alteração')!.disabled).toBeTrue();
    });

    it('obra só com texto legado avisa e permite associar às categorias do catálogo', () => {
      const ctx = setup(of(detail({ genre: 'Culinária', genres: [] })), admin);
      expect(ctx.root.textContent).toContain('Categoria literária: Culinária');
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.textContent).toContain('Texto de categoria anterior: “Culinária”');
    });

    it('mostra as categorias do catálogo no detalhe (não só o texto legado)', () => {
      const { root } = setup(
        of(
          detail({
            genre: 'texto antigo',
            genres: [
              { id: 1, name: 'Ficção', slug: 'ficcao' },
              { id: 7, name: 'Romance', slug: 'romance' },
            ],
          }),
        ),
      );
      expect(root.textContent).toContain('Categoria literária: Ficção, Romance');
    });

    it('mostra erro de domínio sem anunciar sucesso e recarrega', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(
        throwError(() => ({ status: 409, detail: 'Obra não pode ser alterada.' })),
      );
      edit(ctx, ['Ficção']);
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(snackbarMessage()).toContain('Obra não pode ser alterada.');
      expect(snackbarVariant()).toBe('warning');
      expect(snackbarMessage()).not.toContain('atualizada');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });

    it('inativa a obra somente após confirmação e passa a oferecer a reativação', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(of({}) as never);
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      ctx.counter.getCatalogBook.and.returnValue(of(detail({ is_active: false })));
      confirmDialog(ctx);
      expect(ctx.books.update).toHaveBeenCalledOnceWith(7, { is_active: false });
      expect(snackbarMessage()).toContain(
        'Dom Casmurro foi inativada. O histórico foi preservado.',
      );
      expect(ctx.root.textContent).toContain('Situação da obra');
      expect(ctx.root.textContent).toContain('Disponibilidade operacional: indisponível');
      expect(ctx.root.querySelector('a[href="/balcao/acervo"].btn')?.textContent).toContain(
        'Voltar ao acervo',
      );
      expect(ctx.root.textContent).toContain('Status da obra: Inativa');
      expect(ctx.button('Inativar obra')).toBeUndefined();
      expect(ctx.button('Reativar obra')).toBeDefined();
      expect(ctx.root.textContent).not.toContain('A reativação ainda não está disponível.');
    });

    it('o modal de inativação mostra a situação real dos exemplares e a regra de bloqueio', () => {
      const ctx = setup(of(detail()), admin);
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      const dialog = ctx.root.querySelector('dialog')!;
      expect(dialog.querySelector('h2')?.textContent).toBe('Inativar Dom Casmurro?');
      expect(dialog.textContent).toContain('Situação verificada');
      expect(Array.from(dialog.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
        '4 exemplares vinculados',
        'Exemplar 00102 emprestado (bloqueia a inativação)',
        'Exemplar 00104 reservado para venda (bloqueia a inativação)',
      ]);
      expect(dialog.textContent).toContain(
        'bloqueada enquanto houver empréstimo em aberto, solicitação de retirada pendente ou reserva de compra',
      );
      expect(dialog.textContent).not.toContain('O sistema não impede');
      expect(dialog.textContent).toContain('Confirmar inativação');
    });

    it('o modal informa quando não há empréstimo nem reserva', () => {
      const ctx = setup(of(detail({ copies: [copy()], total_copies: 1 })), admin);
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      expect(
        Array.from(ctx.root.querySelectorAll('dialog li')).map((li) => li.textContent),
      ).toEqual(['1 exemplar vinculado', 'Nenhum exemplar emprestado ou reservado para venda']);
    });

    it('mostra o erro de domínio da inativação sem inventar bloqueio nem anunciar sucesso', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(
        throwError(() => ({ status: 409, detail: 'Obra não pode ser inativada.' })),
      );
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(snackbarMessage()).toContain('Obra não pode ser inativada.');
      expect(snackbarMessage()).not.toContain('foi inativada');
      expect(ctx.root.textContent).not.toContain('Vínculos encontrados');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });

    it('bloqueia duplo envio da inativação', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(new Subject<unknown>() as never);
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      expect(ctx.books.update).toHaveBeenCalledTimes(1);
    });

    it('estoquista pode abrir o gerenciamento de categorias e situação', () => {
      const keeper = setup(of(detail()), ['STOCK_KEEPER']);
      expect(keeper.button('Editar categorias')).toBeDefined();
      expect(keeper.root.querySelector('app-genre-picker')).toBeNull();
    });

    it('mostra a inativação bloqueada com os vínculos devolvidos pelo 409 e não anuncia sucesso', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(
        throwError(() => ({
          status: 409,
          code: 'book_has_active_operations',
          detail: 'Esta obra possui operações em andamento e não pode ser inativada.',
          details: {
            counts: { open_loans: 1, pending_loan_requests: 0, purchase_reservations: 1 },
            links: [
              { type: 'open_loan', copy_barcode: '00102', client_name: 'Maria Silva' },
              { type: 'purchase_reservation', copy_barcode: null, client_name: 'Ana Santos' },
            ],
          },
        })),
      );
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      const blocked = ctx.root.querySelector('[data-blocked]')!;
      expect(blocked.querySelector('h2')?.textContent).toBe('Inativação bloqueada');
      expect(blocked.textContent).toContain('Esta obra possui operações ativas');
      expect(blocked.textContent).toContain('Regularize os vínculos antes de tentar inativar.');
      expect(blocked.textContent).toContain('Vínculos encontrados');
      expect(Array.from(blocked.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
        'Empréstimos em aberto: 1',
        'Reservas de compra aguardando ou com exemplar destinado: 1',
        'Exemplar #00102 · empréstimo ativo · Maria Silva',
        'reserva de compra · Ana Santos',
      ]);
      expect(blocked.querySelector('a[href="/balcao/emprestimos/ativos"]')?.textContent).toContain(
        'Consultar empréstimos',
      );
      expect(blocked.querySelector('a[href="/balcao/reservas"]')?.textContent).toContain(
        'Consultar reservas',
      );
      expect(ctx.root.querySelector('app-alert')).toBeNull();
      expect(snackbarMessage()).not.toContain('foi inativada');
      expect(ctx.root.textContent).toContain('Status da obra: Ativa');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });
  });

  it('pagina exemplares de cinco em cinco e reinicia ao trocar o filtro', () => {
    const copies = Array.from({ length: 7 }, (_, i) =>
      copy({ id: i + 1, barcode: `C${i + 1}`, destination: i < 6 ? 'DIDACTIC' : 'COMMERCIAL' }),
    );
    const ctx = setup(of(detail({ copies, total_copies: 7 })));
    expect(ctx.root.querySelectorAll('tbody tr').length).toBe(5);
    expect(ctx.root.querySelector('.copy-pagination')?.textContent).toContain('Página 1 de 2');
    ctx.button('Próxima →')!.click();
    ctx.fixture.detectChanges();
    expect(ctx.root.querySelectorAll('tbody tr').length).toBe(2);
    expect(ctx.button('Próxima →')!.disabled).toBeTrue();
    const filter = ctx.root.querySelector('#copy-filter') as HTMLSelectElement;
    filter.value = 'COMMERCIAL';
    filter.dispatchEvent(new Event('change'));
    ctx.fixture.detectChanges();
    expect(ctx.root.querySelectorAll('tbody tr').length).toBe(1);
    expect(ctx.root.querySelector('tbody')?.textContent).toContain('C7');
    expect(ctx.root.querySelector('.copy-pagination')).toBeNull();
  });

  it('cancela a edição de categorias sem persistir e restaura a seleção', () => {
    const ctx = setup(of(detail()));
    edit(ctx, ['Fantasia']);
    ctx.button('Cancelar edição de categorias')!.click();
    ctx.fixture.detectChanges();
    expect(ctx.root.querySelector('app-genre-picker')).toBeNull();
    expect(ctx.books.update).not.toHaveBeenCalled();
    ctx.button('Editar categorias')!.click();
    ctx.fixture.detectChanges();
    expect((ctx.root.querySelector('#book-genre-7') as HTMLInputElement).checked).toBeTrue();
    expect((ctx.root.querySelector('#book-genre-4') as HTMLInputElement).checked).toBeFalse();
  });

  it('fecha a gestão do exemplar sem alterar o estoque', () => {
    const ctx = setup(of(detail()));
    selectCopy(ctx);
    expect(ctx.root.querySelector('[data-copy-management]')).not.toBeNull();
    ctx.button('Fechar')!.click();
    ctx.fixture.detectChanges();
    expect(ctx.root.querySelector('[data-copy-management]')).toBeNull();
    expect(ctx.copies.update).not.toHaveBeenCalled();
    expect(ctx.copies.delete).not.toHaveBeenCalled();
  });

  it('inativa e reativa pelo painel somente após confirmar', () => {
    const ctx = setup(of(detail()));
    ctx.copies.update.and.returnValue(of({}) as never);
    selectCopy(ctx);
    ctx.button('Inativar')!.click();
    ctx.fixture.detectChanges();
    expect(ctx.copies.update).not.toHaveBeenCalled();
    ctx.counter.getCatalogBook.and.returnValue(
      of(
        detail({
          copies: [
            copy({ is_active: false, status: 'INACTIVE', free: false }),
            ...detail().copies.slice(1),
          ],
        }),
      ),
    );
    confirmDialog(ctx);
    expect(ctx.copies.update).toHaveBeenCalledWith(1, { isActive: false });
    selectCopy(ctx);
    ctx.button('Reativar')!.click();
    ctx.fixture.detectChanges();
    confirmDialog(ctx);
    expect(ctx.copies.update).toHaveBeenCalledWith(1, { isActive: true });
  });

  describe('exclusão de exemplar', () => {
    const admin: RoleCode[] = ['ADMINISTRATOR'];
    function openDelete(ctx: Ctx, row = 0) {
      deleteButton(ctx, row).click();
      ctx.fixture.detectChanges();
    }

    it('mantém a tabela limpa e oferece gestão somente aos papéis autorizados', () => {
      expect(setup(of(detail()), ['USER']).root.querySelector('.copy-code')).toBeNull();
      for (const role of ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR'] as RoleCode[]) {
        TestBed.resetTestingModule();
        const ctx = setup(of(detail()), [role]);
        expect(ctx.root.querySelector('[data-copy-management]')).toBeNull();
        expect(ctx.root.querySelector('thead')?.textContent).not.toContain('Ações');
        expect(deleteButton(ctx)).not.toBeNull();
      }
    });

    it('informa os bloqueios apenas no exemplar selecionado', () => {
      const ctx = setup(of(detail()), admin);
      expect([0, 1, 2, 3].map((row) => deleteButton(ctx, row).disabled)).toEqual([
        false,
        true,
        false,
        true,
      ]);
      expect(deleteButton(ctx, 1).title).toContain('Exemplar emprestado');
      expect(ctx.root.querySelector('[data-copy-management]')?.textContent).toContain(
        'Exemplar emprestado',
      );
      expect(deleteButton(ctx, 3).title).toContain('Exemplar reservado para venda');
    });

    it('bloqueia excluir o último exemplar de obra ativa', () => {
      const only = setup(of(detail({ copies: [copy()], total_copies: 1 })), admin);
      expect(deleteButton(only).disabled).toBeTrue();
      expect(only.root.textContent).toContain('Último exemplar ativo da obra');
      TestBed.resetTestingModule();
      const inactive = setup(
        of(detail({ copies: [copy()], total_copies: 1, is_active: false })),
        admin,
      );
      expect(deleteButton(inactive).disabled).toBeFalse();
    });

    it('abre o modal conforme o design com a contagem antes e depois, sem excluir antes de confirmar', () => {
      const ctx = setup(of(detail()), admin);
      openDelete(ctx);
      const dialog = ctx.root.querySelector('dialog')!;
      expect(dialog.querySelector('h2')?.textContent).toBe('Excluir exemplar #00101?');
      expect(dialog.textContent).toContain(
        'Você está excluindo somente esta cópia de Dom Casmurro. A obra e os outros exemplares serão mantidos.',
      );
      expect(dialog.textContent).toContain('Confira o exemplar');
      expect(Array.from(dialog.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
        '#00101 · Empréstimo · Disponível',
        'Quantidade da obra após exclusão: 4 → 3',
        'Esta ação remove a cópia do acervo.',
      ]);
      expect(ctx.copies.delete).not.toHaveBeenCalled();
      ctx.button('Cancelar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('dialog')).toBeNull();
      expect(ctx.copies.delete).not.toHaveBeenCalled();
    });

    it('exclui só após confirmar, bloqueia duplo envio, avisa o sucesso e recarrega a obra', () => {
      const ctx = setup(of(detail()), admin);
      const request = new Subject<unknown>();
      ctx.copies.delete.and.returnValue(request as never);
      openDelete(ctx);
      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      ctx.fixture.detectChanges();
      expect(ctx.copies.delete).toHaveBeenCalledOnceWith(1);
      expect(snackbarMessage()).not.toContain('Exemplar #00101 excluído');
      ctx.counter.getCatalogBook.and.returnValue(
        of(detail({ total_copies: 3, copies: detail().copies.slice(1) })),
      );
      request.next({ id: 1, bookId: 7, barcode: '00101' });
      request.complete();
      ctx.fixture.detectChanges();
      expect(snackbarMessage()).toContain(
        'Exemplar #00101 excluído. A quantidade de Dom Casmurro foi atualizada de 4 para 3 exemplares.',
      );
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
    });

    it('mostra Exclusão bloqueada com os motivos do backend e recarrega sem anunciar sucesso', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValue(
        throwError(() => ({
          status: 409,
          code: 'copy_has_history',
          detail: 'Este exemplar possui histórico.',
          details: {
            reasons: [
              {
                code: 'copy_has_history',
                message:
                  'O exemplar possui histórico de empréstimo, venda, reserva ou solicitação.',
              },
            ],
            history: { loans: 2, sales: 0, purchase_reservations: 1, requests: 0 },
          },
        })),
      );
      openDelete(ctx, 2);
      confirmDialog(ctx);
      const blocked = ctx.root.querySelector('[data-blocked]')!;
      expect(blocked.querySelector('h2')?.textContent).toBe('Exclusão bloqueada');
      expect(blocked.textContent).toContain('Este exemplar possui histórico.');
      expect(blocked.textContent).toContain(
        'A exclusão não pode ser concluída enquanto houver operação ativa ou histórico.',
      );
      expect(Array.from(blocked.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
        'O exemplar possui histórico de empréstimo, venda, reserva ou solicitação.',
        'Empréstimos: 2',
        'Reservas de compra: 1',
      ]);
      expect(snackbarMessage()).not.toContain('Exemplar #00101 excluído');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      ctx.button('Voltar aos exemplares')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
    });

    it('mostra os vínculos sem nome de cliente quando o backend o omite', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(
        throwError(() => ({
          status: 409,
          code: 'book_has_active_operations',
          detail: 'x',
          details: {
            counts: { open_loans: 1 },
            links: [{ type: 'open_loan', copy_barcode: '00102' }],
          },
        })),
      );
      ctx.button('Editar categorias')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(
        Array.from(ctx.root.querySelectorAll('[data-blocked] li')).map((li) => li.textContent),
      ).toEqual(['Empréstimos em aberto: 1', 'Exemplar #00102 · empréstimo ativo']);
    });

    it('salvar a categoria limpa um bloqueio anterior', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValue(
        throwError(() => ({
          status: 409,
          code: 'copy_not_available',
          detail: 'x',
          details: { reasons: [{ message: 'm' }] },
        })),
      );
      ctx.books.update.and.returnValue(of({}) as never);
      deleteButton(ctx).click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[data-blocked]')).not.toBeNull();
      edit(ctx, ['Ficção']);
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
    });

    it('trata falhas que não são bloqueio como erro genérico, sem tela de bloqueio', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValue(
        throwError(() => ({
          status: 500,
          code: 'copy_delete_persistence_error',
          detail: 'Não foi possível excluir o exemplar. Nada foi alterado; tente novamente.',
        })),
      );
      openDelete(ctx);
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
      expect(ctx.root.querySelector('app-save-failure')?.textContent).toContain(
        'Não foi possível salvar',
      );
      expect(ctx.root.querySelector('app-save-failure')?.textContent).toContain(
        'Atualize a consulta antes de repetir',
      );
      expect(snackbarMessage()).toBe('');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(snackbarMessage()).not.toContain('Exemplar #00101 excluído');
    });

    it('depois de excluir, a tela de bloqueio anterior some', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValues(
        throwError(() => ({
          status: 409,
          code: 'copy_not_available',
          detail: 'Indisponível.',
          details: { reasons: [{ message: 'Não disponível.' }] },
        })),
        of({ id: 1, bookId: 7, barcode: '00101' }),
      );
      openDelete(ctx);
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[data-blocked]')).not.toBeNull();
      openDelete(ctx);
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
      confirmDialog(ctx);
      expect(snackbarMessage()).toContain('Exemplar #00101 excluído.');
    });
  });

  describe('reativação de obra', () => {
    const inactive = (over: Partial<StaffCatalogBookDetail> = {}) =>
      detail({ is_active: false, ...over });

    it('oferece Reativar obra a SELLER e ADMINISTRATOR, e não a quem não administra o acervo', () => {
      expect(setup(of(inactive()), ['STOCK_KEEPER']).button('Reativar obra')).toBeDefined();
      TestBed.resetTestingModule();
      expect(setup(of(inactive()), ['SELLER']).button('Reativar obra')).toBeDefined();
      TestBed.resetTestingModule();
      expect(setup(of(inactive()), ['ADMINISTRATOR']).button('Reativar obra')).toBeDefined();
      TestBed.resetTestingModule();
      expect(setup(of(inactive()), ['USER']).button('Reativar obra')).toBeUndefined();
      TestBed.resetTestingModule();
      expect(setup(of(detail()), ['SELLER']).button('Reativar obra')).toBeUndefined();
    });

    it('pede confirmação, bloqueia duplo envio e só anuncia sucesso após 2xx, recarregando', () => {
      const ctx = setup(of(inactive()), ['SELLER']);
      const request = new Subject<unknown>();
      ctx.books.update.and.returnValue(request as never);
      ctx.button('Reativar obra')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
      expect(ctx.root.textContent).toContain('Reativar Dom Casmurro?');
      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).toHaveBeenCalledOnceWith(7, { is_active: true });
      expect(snackbarMessage()).not.toContain('foi reativada');
      ctx.counter.getCatalogBook.and.returnValue(of(detail()));
      request.next({});
      request.complete();
      ctx.fixture.detectChanges();
      expect(snackbarMessage()).toContain('Dom Casmurro foi reativada.');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(ctx.root.textContent).toContain('Status da obra: Ativa');
    });

    it('cancelar não altera nada', () => {
      const ctx = setup(of(inactive()), ['SELLER']);
      ctx.button('Reativar obra')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Cancelar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.books.update).not.toHaveBeenCalled();
    });

    it('antecipa o bloqueio sem exemplar ativo e não chama o backend', () => {
      const ctx = setup(
        of(inactive({ copies: [copy({ is_active: false, status: 'INACTIVE', free: false })] })),
        ['SELLER'],
      );
      expect(ctx.button('Reativar obra')!.disabled).toBeTrue();
      expect(ctx.root.textContent).toContain('A obra não tem exemplar ativo');
      ctx.button('Reativar obra')!.click();
      expect(ctx.books.update).not.toHaveBeenCalled();
    });

    it('mostra o erro de domínio do backend sem anunciar sucesso e recarrega', () => {
      const ctx = setup(of(inactive()), ['SELLER']);
      ctx.books.update.and.returnValue(
        throwError(() => ({
          status: 409,
          code: 'book_without_active_copy',
          detail: 'A obra não pode ser reativada sem ao menos um exemplar ativo.',
        })) as never,
      );
      ctx.button('Reativar obra')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(snackbarMessage()).toContain('não pode ser reativada sem ao menos um exemplar ativo');
      expect(snackbarVariant()).toBe('warning');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });
  });

  describe('edição e conversão de exemplar', () => {
    const seller: RoleCode[] = ['SELLER'];
    const rowButton = (ctx: Ctx, row: number, label: string) => {
      selectCopy(ctx, row);
      return Array.from(ctx.root.querySelectorAll('[data-copy-management] button')).find(
        (b) => b.textContent?.trim() === label,
      ) as HTMLButtonElement;
    };
    function open(ctx: Ctx, row: number) {
      rowButton(ctx, row, 'Editar').click();
      ctx.fixture.detectChanges();
    }

    function type(ctx: Ctx, selector: string, value: string, event = 'input') {
      const field = ctx.root.querySelector(selector) as HTMLInputElement | HTMLSelectElement;
      field.value = value;
      field.dispatchEvent(new Event(event));
      ctx.fixture.detectChanges();
    }

    it('só oferece Editar a papéis autorizados e o desabilita com o motivo quando o exemplar não é editável', () => {
      const ctx = setup(of(detail()), seller);
      expect([0, 1, 2, 3].map((row) => rowButton(ctx, row, 'Editar')!.disabled)).toEqual([
        false,
        true,
        false,
        true,
      ]);
      expect(rowButton(ctx, 1, 'Editar')!.title).toBe(
        'Exemplar emprestado: só exemplares disponíveis podem ser editados.',
      );
      expect(rowButton(ctx, 3, 'Editar')!.title).toBe(
        'Exemplar reservado para venda: não pode ser editado.',
      );
      TestBed.resetTestingModule();
      expect(setup(of(detail()), ['USER']).root.textContent).not.toContain('Editar exemplar');
      TestBed.resetTestingModule();
      expect(rowButton(setup(of(detail()), ['STOCK_KEEPER']), 0, 'Editar')).toBeDefined();
    });

    it('abre o painel "Editando exemplar" com o código imutável e os dados atuais', () => {
      const ctx = setup(of(detail()), seller);
      open(ctx, 2);
      expect(ctx.root.querySelector('#editar-exemplar-titulo')?.textContent).toBe(
        'Editando exemplar #00103',
      );
      expect(ctx.root.textContent).toContain('Obra: Dom Casmurro');
      const code = ctx.root.querySelector('#copy-barcode') as HTMLInputElement;
      expect([code.value, code.readOnly]).toEqual(['00103', true]);
      expect((ctx.root.querySelector('#copy-destination') as HTMLSelectElement).value).toBe(
        'COMMERCIAL',
      );
      expect((ctx.root.querySelector('#copy-price') as HTMLInputElement).value).toBe('39,90');
      expect(ctx.button('Salvar exemplar')!.disabled).toBeTrue();
      ctx.button('Cancelar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('[data-copy-panel]')).toBeNull();
    });

    it('converte para Venda exigindo preço maior que zero e envia só o que mudou, após confirmar', () => {
      const ctx = setup(of(detail()), seller);
      const request = new Subject<unknown>();
      ctx.copies.update.and.returnValue(request as never);
      open(ctx, 0);
      type(ctx, '#copy-destination', 'COMMERCIAL', 'change');
      expect(ctx.root.textContent).toContain('Informe o preço de venda');
      expect(ctx.button('Salvar exemplar')!.disabled).toBeTrue();
      type(ctx, '#copy-price', '0');
      expect(ctx.root.textContent).toContain('maior que zero');
      type(ctx, '#copy-price', '29,5');
      expect(ctx.button('Salvar exemplar')!.disabled).toBeFalse();
      ctx.button('Salvar exemplar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.copies.update).not.toHaveBeenCalled();
      expect(ctx.root.textContent).toContain('Finalidade: Empréstimo → Venda');
      expect(ctx.root.textContent).toContain('Preço de venda: — → R$');
      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      ctx.fixture.detectChanges();
      expect(ctx.copies.update).toHaveBeenCalledOnceWith(1, {
        destination: 'COMMERCIAL',
        salePrice: 29.5,
      });
      expect(snackbarMessage()).not.toContain('atualizado');
      ctx.counter.getCatalogBook.and.returnValue(
        of(
          detail({
            copies: [
              copy({ destination: 'COMMERCIAL', sale_price: '29.50' }),
              ...detail().copies.slice(1),
            ],
          }),
        ),
      );
      request.next({});
      request.complete();
      ctx.fixture.detectChanges();
      expect(snackbarMessage()).toContain('Exemplar #00101 atualizado.');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(ctx.root.querySelector('[data-copy-panel]')).toBeNull();
    });

    it('converte para Empréstimo sem enviar preço', () => {
      const ctx = setup(of(detail()), seller);
      ctx.copies.update.and.returnValue(of({}) as never);
      open(ctx, 2);
      type(ctx, '#copy-destination', 'DIDACTIC', 'change');
      expect(ctx.root.querySelector('#copy-price')).toBeNull();
      expect(ctx.root.textContent).toContain('Converter para Empréstimo remove o preço de venda');
      ctx.button('Salvar exemplar')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.textContent).toContain('Preço de venda: R$');
      expect(ctx.root.textContent).toContain('removido');
      confirmDialog(ctx);
      expect(ctx.copies.update).toHaveBeenCalledOnceWith(3, { destination: 'DIDACTIC' });
    });

    it('edita a condição sem converter e limita a 30 caracteres', () => {
      const ctx = setup(of(detail()), seller);
      ctx.copies.update.and.returnValue(of({}) as never);
      open(ctx, 0);
      type(ctx, '#copy-condition', 'x'.repeat(31));
      expect(ctx.root.textContent).toContain('A condição aceita até 30 caracteres.');
      expect(ctx.button('Salvar exemplar')!.disabled).toBeTrue();
      type(ctx, '#copy-condition', ' Bom estado ');
      ctx.button('Salvar exemplar')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(ctx.copies.update).toHaveBeenCalledOnceWith(1, { condition: 'Bom estado' });
    });

    it('mostra o erro de domínio sem anunciar sucesso e recarrega a obra', () => {
      const ctx = setup(of(detail()), seller);
      ctx.copies.update.and.returnValue(
        throwError(() => ({
          status: 409,
          code: 'copy_not_available',
          detail: 'Este exemplar não está disponível para esta operação. Atualize a obra.',
        })) as never,
      );
      open(ctx, 0);
      type(ctx, '#copy-condition', 'Usado');
      ctx.button('Salvar exemplar')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(snackbarMessage()).toContain('não está disponível para esta operação');
      expect(snackbarVariant()).toBe('warning');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });

    it('fecha o painel quando a recarga mostra que o exemplar deixou de ser editável', () => {
      const ctx = setup(of(detail()), seller);
      ctx.copies.update.and.returnValue(
        throwError(() => ({ status: 409, code: 'copy_not_available', detail: 'x' })) as never,
      );
      open(ctx, 0);
      type(ctx, '#copy-condition', 'Usado');
      ctx.button('Salvar exemplar')!.click();
      ctx.fixture.detectChanges();
      ctx.counter.getCatalogBook.and.returnValue(
        of(
          detail({
            copies: [copy({ status: 'BORROWED', free: false }), ...detail().copies.slice(1)],
          }),
        ),
      );
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[data-copy-panel]')).toBeNull();
    });
  });
});
