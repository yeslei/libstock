import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';

import { RoleCode } from '../../core/models/user.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { CopyResponse } from '../copies/models/copy.model';
import { CopyService } from '../copies/services/copy.service';
import { CounterCopyCreateComponent } from './counter-copy-create.component';
import { CounterService, StaffCatalogBookDetail } from './counter.service';

const detail = (over: Partial<StaffCatalogBookDetail> = {}): StaffCatalogBookDetail => ({
  id: 7, title: 'Dom Casmurro', author: 'Machado de Assis', isbn: null, genre: 'Romance', is_active: true,
  total_copies: 4, didactic_copies: 2, commercial_copies: 2, copies: [], ...over,
});

const created = (over: Partial<CopyResponse> = {}): CopyResponse => ({
  id: 9, bookId: 7, barcode: '00105', destination: 'DIDACTIC', condition: null, salePrice: null,
  acquiredAt: null, status: 'AVAILABLE', isActive: true, ...over,
});

function setup(book$: Observable<StaffCatalogBookDetail>, roles: RoleCode[] = ['ADMINISTRATOR']) {
  const counter = jasmine.createSpyObj<CounterService>('CounterService', ['getCatalogBook']);
  counter.getCatalogBook.and.returnValue(book$);
  const copies = jasmine.createSpyObj<CopyService>('CopyService', ['create']);
  TestBed.configureTestingModule({
    imports: [CounterCopyCreateComponent],
    providers: [
      provideRouter([]),
      { provide: CounterService, useValue: counter },
      { provide: CopyService, useValue: copies },
      { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: '7' })) } },
    ],
  });
  TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'A', email: 'a@x.dev', role_codes: roles, created_at: '' });
  const fixture = TestBed.createComponent(CounterCopyCreateComponent);
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  const type = (selector: string, value: string) => {
    const input = root.querySelector(selector) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  };
  const choose = (value: string) => {
    const select = root.querySelector('#copy-destination') as HTMLSelectElement;
    select.value = value;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  };
  const save = () => {
    (root.querySelector('button[type="submit"]') as HTMLButtonElement).click();
    fixture.detectChanges();
  };
  return { fixture, counter, copies, root, type, choose, save };
}

describe('Balcão: novo exemplar', () => {
  it('mostra a obra real e o formulário, sem campo de preço para empréstimo', () => {
    const { root, choose, counter } = setup(of(detail()));
    expect(counter.getCatalogBook).toHaveBeenCalledWith(7);
    expect(root.querySelector('h1')?.textContent).toBe('Novo exemplar');
    expect(root.textContent).toContain('Dom Casmurro · Machado de Assis');
    expect(root.textContent).toContain('Quantidade atual: 4 exemplares');
    expect(root.querySelector('#copy-price')).toBeNull();
    choose('COMMERCIAL');
    expect(root.querySelector('#copy-price')).not.toBeNull();
    choose('DIDACTIC');
    expect(root.querySelector('#copy-price')).toBeNull();
  });

  it('valida campos obrigatórios sem chamar o backend', () => {
    const { root, copies, save } = setup(of(detail()));
    save();
    expect(copies.create).not.toHaveBeenCalled();
    expect(root.textContent).toContain('Informe o código do exemplar.');
    expect(root.textContent).toContain('Escolha a finalidade do exemplar.');
  });

  it('exige preço para venda e rejeita preço inválido', () => {
    const { root, copies, type, choose, save } = setup(of(detail()));
    type('#copy-barcode', '00105');
    choose('COMMERCIAL');
    save();
    expect(root.textContent).toContain('Informe o preço de venda.');
    type('#copy-price', '12.345');
    expect(root.textContent).toContain('com até 10 dígitos e duas casas decimais');
    save();
    expect(copies.create).not.toHaveBeenCalled();
  });

  it('envia exemplar de empréstimo sem preço e confirma só após 2xx, informando a nova quantidade', () => {
    const ctx = setup(of(detail()));
    const post = new Subject<CopyResponse>();
    ctx.copies.create.and.returnValue(post);
    ctx.type('#copy-barcode', ' 00105 ');
    ctx.choose('DIDACTIC');
    ctx.save();
    expect(ctx.copies.create).toHaveBeenCalledOnceWith({
      bookId: 7, barcode: '00105', destination: 'DIDACTIC', condition: null, salePrice: null, acquiredAt: null,
    });
    expect(ctx.root.textContent).not.toContain('cadastrado');
    expect((ctx.root.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeTrue();

    ctx.counter.getCatalogBook.and.returnValue(of(detail({ total_copies: 5 })));
    post.next(created());
    post.complete();
    ctx.fixture.detectChanges();
    expect(ctx.root.querySelector('h1')?.textContent).toBe('Exemplar incluído');
    expect(ctx.root.textContent).toContain('Exemplar 00105 cadastrado.');
    expect(ctx.root.textContent).toContain('atualizada de 4 para 5 exemplares');
    expect(ctx.root.textContent).toContain('Finalidade: Empréstimo · Status: Disponível');
    expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(2);
  });

  it('bloqueia duplo envio enquanto a requisição está pendente', () => {
    const ctx = setup(of(detail()));
    ctx.copies.create.and.returnValue(new Subject<CopyResponse>());
    ctx.type('#copy-barcode', '00105');
    ctx.choose('DIDACTIC');
    ctx.save();
    ctx.save();
    expect(ctx.copies.create).toHaveBeenCalledTimes(1);
  });

  it('envia o preço de venda com vírgula normalizada', () => {
    const ctx = setup(of(detail()));
    ctx.copies.create.and.returnValue(of(created({ destination: 'COMMERCIAL', salePrice: 39.9 })));
    ctx.type('#copy-barcode', '00106');
    ctx.choose('COMMERCIAL');
    ctx.type('#copy-price', '39,90');
    ctx.save();
    expect(ctx.copies.create).toHaveBeenCalledOnceWith({
      bookId: 7, barcode: '00106', destination: 'COMMERCIAL', condition: null, salePrice: 39.9, acquiredAt: null,
    });
    expect(ctx.root.textContent).toContain('Finalidade: Venda');
  });

  it('mantém os dados no código duplicado (409), bloqueia o envio e libera ao trocar o código', () => {
    const ctx = setup(of(detail()));
    ctx.copies.create.and.returnValue(throwError(() => ({ status: 409, detail: 'Já existe um exemplar com este código de barras.' })));
    ctx.type('#copy-barcode', '00103');
    ctx.choose('DIDACTIC');
    ctx.save();
    expect(ctx.root.textContent).toContain('Este código já está cadastrado. Informe outro código para continuar.');
    expect(ctx.root.textContent).toContain('Seus dados foram mantidos');
    expect((ctx.root.querySelector('#copy-barcode') as HTMLInputElement).value).toBe('00103');
    expect((ctx.root.querySelector('#copy-destination') as HTMLSelectElement).value).toBe('DIDACTIC');
    expect((ctx.root.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeTrue();
    expect(ctx.root.querySelector('h1')?.textContent).toBe('Novo exemplar');
    expect(ctx.counter.getCatalogBook).toHaveBeenCalledTimes(1);

    ctx.type('#copy-barcode', '00105');
    expect(ctx.root.textContent).not.toContain('Seus dados foram mantidos');
    expect((ctx.root.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeFalse();
  });

  it('mostra "Não foi possível salvar" em falha 5xx, mantém os dados e não reenvia sozinho', () => {
    const ctx = setup(of(detail()));
    ctx.copies.create.and.returnValue(throwError(() => ({ status: 500, detail: 'Não foi possível cadastrar o exemplar.' })));
    ctx.type('#copy-barcode', '00105');
    ctx.choose('DIDACTIC');
    ctx.save();
    expect(ctx.root.querySelector('app-save-failure')?.textContent).toContain('Não foi possível salvar');
    expect(snackbarMessage()).toBe('');
    expect(ctx.root.querySelector('h1')?.textContent).toBe('Novo exemplar');
    expect((ctx.root.querySelector('#copy-barcode') as HTMLInputElement).value).toBe('00105');
    expect(ctx.copies.create).toHaveBeenCalledTimes(1);
  });

  it('"Adicionar outro" volta ao formulário vazio', () => {
    const ctx = setup(of(detail()));
    ctx.copies.create.and.returnValue(of(created()));
    ctx.type('#copy-barcode', '00105');
    ctx.choose('DIDACTIC');
    ctx.save();
    const another = Array.from(ctx.root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Adicionar outro')!;
    another.click();
    ctx.fixture.detectChanges();
    expect(ctx.root.querySelector('h1')?.textContent).toBe('Novo exemplar');
    expect((ctx.root.querySelector('#copy-barcode') as HTMLInputElement).value).toBe('');
  });

  it('oferece o formulário ao vendedor, mas não a papéis sem permissão nem para obra inativa', () => {
    const seller = setup(of(detail()), ['SELLER']);
    expect(seller.root.querySelector('form')).not.toBeNull();
    TestBed.resetTestingModule();
    const user = setup(of(detail()), ['USER']);
    expect(user.root.textContent).toContain('Você não tem permissão para incluir exemplares.');
    expect(user.root.querySelector('form')).toBeNull();
    TestBed.resetTestingModule();
    const inactive = setup(of(detail({ is_active: false })));
    expect(inactive.root.textContent).toContain('A obra está inativa e não aceita novos exemplares.');
    expect(inactive.root.querySelector('form')).toBeNull();
  });

  it('mostra erro de carregamento com nova tentativa', () => {
    const { root } = setup(throwError(() => ({ detail: 'Obra não encontrada.' })));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Obra não encontrada.');
  });
});
