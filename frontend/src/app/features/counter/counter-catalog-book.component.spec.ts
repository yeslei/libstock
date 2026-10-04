import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';

import { RoleCode } from '../../core/models/user.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { BookService } from '../books/services/book.service';
import { CopyService } from '../copies/services/copy.service';
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
  const copies = jasmine.createSpyObj<CopyService>('CopyService', ['delete']);
  TestBed.configureTestingModule({
    imports: [CounterCatalogBookComponent],
    providers: [
      provideRouter([]),
      { provide: CounterService, useValue: counter },
      { provide: BookService, useValue: books },
      { provide: CopyService, useValue: copies },
      { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: '7' })) } },
    ],
  });
  TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: roles, created_at: '' });
  const fixture = TestBed.createComponent(CounterCatalogBookComponent);
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  const button = (label: string) =>
    Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label) as HTMLButtonElement | undefined;
  return { fixture, counter, books, copies, root, button };
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

const deleteButtonsOf = (root: HTMLElement) =>
  Array.from(root.querySelectorAll('tbody tr')).map((row) => row.querySelector('button') as HTMLButtonElement | null);

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
      expect(snackbarMessage()).not.toContain('atualizada');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(1);

      ctx.counter.getCatalogBook.and.returnValue(of(detail({ genre: 'Ficção' })));
      patch.next({});
      patch.complete();
      ctx.fixture.detectChanges();
      expect(snackbarMessage()).toContain('Categoria de “Dom Casmurro” atualizada.');
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
      expect(snackbarMessage()).toContain('Obra não pode ser alterada.');
      expect(snackbarVariant()).toBe('warning');
      expect(snackbarMessage()).not.toContain('atualizada');
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
      expect(snackbarMessage()).toContain('Dom Casmurro foi inativada. O histórico foi preservado.');
      expect(ctx.root.textContent).toContain('Situação da obra');
      expect(ctx.root.textContent).toContain('Disponibilidade operacional: indisponível');
      expect(ctx.root.querySelector('a[href="/balcao/acervo"].btn')?.textContent).toContain('Voltar ao acervo');
      expect(ctx.root.textContent).toContain('Status da obra: Inativa');
      expect(ctx.button('Inativar obra')).toBeUndefined();
      expect(ctx.root.textContent).toContain('A reativação ainda não está disponível.');
    });

    it('o modal de inativação mostra a situação real dos exemplares e a regra de bloqueio', () => {
      const ctx = setup(of(detail()), admin);
      ctx.button('Editar obra')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      const dialog = ctx.root.querySelector('dialog')!;
      expect(dialog.querySelector('h2')?.textContent).toBe('Inativar Dom Casmurro?');
      expect(dialog.textContent).toContain('Situação verificada');
      expect(Array.from(dialog.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
        '4 exemplares vinculados', 'Exemplar 00102 emprestado (bloqueia a inativação)',
        'Exemplar 00104 reservado para venda (bloqueia a inativação)',
      ]);
      expect(dialog.textContent).toContain('bloqueada enquanto houver empréstimo em aberto, solicitação de retirada pendente ou reserva de compra');
      expect(dialog.textContent).not.toContain('O sistema não impede');
      expect(dialog.textContent).toContain('Confirmar inativação');
    });

    it('o modal informa quando não há empréstimo nem reserva', () => {
      const ctx = setup(of(detail({ copies: [copy()], total_copies: 1 })), admin);
      ctx.button('Editar obra')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      expect(Array.from(ctx.root.querySelectorAll('dialog li')).map((li) => li.textContent)).toEqual([
        '1 exemplar vinculado', 'Nenhum exemplar emprestado ou reservado para venda',
      ]);
    });

    it('mostra o erro de domínio da inativação sem inventar bloqueio nem anunciar sucesso', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(throwError(() => ({ status: 409, detail: 'Obra não pode ser inativada.' })));
      ctx.button('Editar obra')!.click();
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
      ctx.button('Editar obra')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      const submit = ctx.root.querySelector('.confirm__submit') as HTMLButtonElement;
      submit.click();
      submit.click();
      expect(ctx.books.update).toHaveBeenCalledTimes(1);
    });

    it('oferece edição também a STOCK_KEEPER, papel autorizado pelo backend', () => {
      const keeper = setup(of(detail()), ['STOCK_KEEPER']);
      expect(keeper.button('Editar obra')).toBeDefined();
    });

    it('mostra a inativação bloqueada com os vínculos devolvidos pelo 409 e não anuncia sucesso', () => {
      const ctx = setup(of(detail()), admin);
      ctx.books.update.and.returnValue(throwError(() => ({
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
      })));
      ctx.button('Editar obra')!.click();
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
      expect(blocked.querySelector('a[href="/balcao/emprestimos/ativos"]')?.textContent).toContain('Consultar empréstimos');
      expect(blocked.querySelector('a[href="/balcao/reservas"]')?.textContent).toContain('Consultar reservas');
      expect(ctx.root.querySelector('app-alert')).toBeNull();
      expect(snackbarMessage()).not.toContain('foi inativada');
      expect(ctx.root.textContent).toContain('Status da obra: Ativa');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
    });
  });

  describe('exclusão de exemplar', () => {
    const admin: RoleCode[] = ['ADMINISTRATOR'];
    const deleteButtons = (root: HTMLElement) =>
      Array.from(root.querySelectorAll('tbody tr')).map((row) => row.querySelector('button') as HTMLButtonElement | null);

    function openDelete(ctx: Ctx, row = 0) {
      deleteButtons(ctx.root)[row]!.click();
      ctx.fixture.detectChanges();
    }

    it('só oferece a ação a papéis autorizados no backend', () => {
      expect(deleteButtons(setup(of(detail()), ['SELLER']).root).every((b) => b === null)).toBeTrue();
      TestBed.resetTestingModule();
      expect(deleteButtons(setup(of(detail()), ['STOCK_KEEPER']).root).length).toBe(4);
      TestBed.resetTestingModule();
      const { root } = setup(of(detail()), admin);
      expect(root.querySelector('thead')?.textContent).toContain('Ações');
    });

    it('antecipa o botão desabilitado com o motivo quando o status já indica bloqueio', () => {
      const { root } = setup(of(detail()), admin);
      const buttons = deleteButtons(root);
      expect(buttons.map((b) => b!.disabled)).toEqual([false, true, false, true]);
      expect(buttons[1]!.title).toBe('Exemplar emprestado: só exemplares disponíveis podem ser excluídos.');
      expect(buttons[3]!.title).toBe('Exemplar reservado para venda: não pode ser excluído.');
      expect(root.querySelector('#excluir-motivo-2')?.textContent).toContain('Exemplar emprestado');
    });

    it('antecipa o bloqueio do último exemplar ativo de obra ativa, mas não de obra inativa', () => {
      const only = setup(of(detail({ copies: [copy()], total_copies: 1 })), admin);
      expect(deleteButtons(only.root)[0]!.disabled).toBeTrue();
      expect(only.root.textContent).toContain('Último exemplar ativo da obra');
      TestBed.resetTestingModule();
      const inactive = setup(of(detail({ copies: [copy()], total_copies: 1, is_active: false })), admin);
      expect(deleteButtons(inactive.root)[0]!.disabled).toBeFalse();
    });

    it('abre o modal conforme o design com a contagem antes e depois, sem excluir antes de confirmar', () => {
      const ctx = setup(of(detail()), admin);
      openDelete(ctx);
      const dialog = ctx.root.querySelector('dialog')!;
      expect(dialog.querySelector('h2')?.textContent).toBe('Excluir exemplar #00101?');
      expect(dialog.textContent).toContain('Você está excluindo somente esta cópia de Dom Casmurro. A obra e os outros exemplares serão mantidos.');
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
      ctx.counter.getCatalogBook.and.returnValue(of(detail({ total_copies: 3, copies: detail().copies.slice(1) })));
      request.next({ id: 1, bookId: 7, barcode: '00101' });
      request.complete();
      ctx.fixture.detectChanges();
      expect(snackbarMessage()).toContain('Exemplar #00101 excluído. A quantidade de Dom Casmurro foi atualizada de 4 para 3 exemplares.');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(ctx.root.textContent).toContain('Quantidade total: 3 exemplares');
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
    });

    it('mostra Exclusão bloqueada com os motivos do backend e recarrega sem anunciar sucesso', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValue(throwError(() => ({
        status: 409,
        code: 'copy_has_history',
        detail: 'Este exemplar possui histórico.',
        details: {
          reasons: [{ code: 'copy_has_history', message: 'O exemplar possui histórico de empréstimo, venda, reserva ou solicitação.' }],
          history: { loans: 2, sales: 0, purchase_reservations: 1, requests: 0 },
        },
      })));
      openDelete(ctx, 2);
      confirmDialog(ctx);
      const blocked = ctx.root.querySelector('[data-blocked]')!;
      expect(blocked.querySelector('h2')?.textContent).toBe('Exclusão bloqueada');
      expect(blocked.textContent).toContain('Este exemplar possui histórico.');
      expect(blocked.textContent).toContain('A exclusão não pode ser concluída enquanto houver operação ativa ou histórico.');
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
      ctx.books.update.and.returnValue(throwError(() => ({
        status: 409, code: 'book_has_active_operations', detail: 'x',
        details: { counts: { open_loans: 1 }, links: [{ type: 'open_loan', copy_barcode: '00102' }] },
      })));
      ctx.button('Editar obra')!.click();
      ctx.fixture.detectChanges();
      ctx.button('Inativar obra')!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(Array.from(ctx.root.querySelectorAll('[data-blocked] li')).map((li) => li.textContent)).toEqual([
        'Empréstimos em aberto: 1', 'Exemplar #00102 · empréstimo ativo',
      ]);
    });

    it('salvar a categoria limpa um bloqueio anterior', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValue(throwError(() => ({ status: 409, code: 'copy_not_available', detail: 'x', details: { reasons: [{ message: 'm' }] } })));
      ctx.books.update.and.returnValue(of({}) as never);
      deleteButtonsOf(ctx.root)[0]!.click();
      ctx.fixture.detectChanges();
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[data-blocked]')).not.toBeNull();
      edit(ctx, 'Ficção');
      ctx.button('Salvar alteração')!.click();
      ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
    });

    it('trata falhas que não são bloqueio como erro genérico, sem tela de bloqueio', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValue(throwError(() => ({ status: 500, code: 'copy_delete_persistence_error', detail: 'Não foi possível excluir o exemplar. Nada foi alterado; tente novamente.' })));
      openDelete(ctx);
      confirmDialog(ctx);
      expect(ctx.root.querySelector('[data-blocked]')).toBeNull();
      expect(ctx.root.querySelector('app-save-failure')?.textContent).toContain('Não foi possível salvar');
      expect(ctx.root.querySelector('app-save-failure')?.textContent).toContain('Atualize a consulta antes de repetir');
      expect(snackbarMessage()).toBe('');
      expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
      expect(snackbarMessage()).not.toContain('Exemplar #00101 excluído');
    });

    it('depois de excluir, a tela de bloqueio anterior some', () => {
      const ctx = setup(of(detail()), admin);
      ctx.copies.delete.and.returnValues(
        throwError(() => ({ status: 409, code: 'copy_not_available', detail: 'Indisponível.', details: { reasons: [{ message: 'Não disponível.' }] } })),
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
});
