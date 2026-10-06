import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { BookService } from '../../books/services/book.service';
import { CopyService } from '../services/copy.service';
import { CopyBatchCreateComponent } from './copy-batch-create.component';

describe('Cadastro de exemplares em lote', () => {
  let fixture: ComponentFixture<CopyBatchCreateComponent>;
  let copies: jasmine.SpyObj<CopyService>;
  const book = {
    id: 7,
    title: 'Dom Casmurro',
    author: 'Machado',
    genre: null,
    isbn: null,
    cover_url: null,
    is_active: true,
    initial_copy: null,
    copies: [],
  };
  const result = {
    id: 1,
    bookId: 7,
    barcode: 'EX-1',
    destination: 'DIDACTIC' as const,
    condition: null,
    salePrice: null,
    acquiredAt: null,
    status: 'AVAILABLE' as const,
    isActive: true,
  };
  beforeEach(async () => {
    copies = jasmine.createSpyObj('CopyService', ['createBatch']);
    copies.createBatch.and.returnValue(of([result]));
    await TestBed.configureTestingModule({
      imports: [CopyBatchCreateComponent],
      providers: [
        provideRouter([]),
        { provide: BookService, useValue: { get: () => of(book) } },
        { provide: CopyService, useValue: copies },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '7' }), queryParams: {} } },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CopyBatchCreateComponent);
    fixture.detectChanges();
  });
  const root = () => fixture.nativeElement as HTMLElement;
  function clickText(text: string) {
    [...root().querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.trim() === text)!
      .click();
    fixture.detectChanges();
  }
  function input(selector: string, value: string, event = 'input') {
    const el = root().querySelector<HTMLInputElement>(selector)!;
    el.value = value;
    el.dispatchEvent(new Event(event));
    fixture.detectChanges();
  }
  function generate(quantity: number) {
    input('#batch-quantity', String(quantity));
    clickText('Preparar códigos');
  }
  function submit() {
    root().querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }
  it('gera códigos únicos para a quantidade e envia uma transação de lote', () => {
    generate(3);
    expect(root().querySelectorAll('.queue li').length).toBe(3);
    submit();
    const payload = copies.createBatch.calls.mostRecent().args[0];
    expect(payload.length).toBe(3);
    expect(new Set(payload.map((copy) => copy.barcode)).size).toBe(3);
    expect(
      payload.every((copy) => copy.bookId === 7 && copy.destination === 'DIDACTIC'),
    ).toBeTrue();
    expect(root().textContent).toContain('cadastrado(s) com sucesso');
  });
  it('Enter do leitor adiciona sem salvar e mantém o campo pronto', () => {
    clickText('Ler ou digitar');
    input('#scan-code', 'EX-1');
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    root().querySelector('#scan-code')!.dispatchEvent(event);
    fixture.detectChanges();
    expect(event.defaultPrevented).toBeTrue();
    expect(copies.createBatch).not.toHaveBeenCalled();
    expect(root().querySelectorAll('.queue li').length).toBe(1);
    expect(root().querySelector<HTMLInputElement>('#scan-code')!.value).toBe('');
    input('#scan-code', 'EX-1');
    clickText('Adicionar à lista');
    expect(root().textContent).toContain('Códigos repetidos');
    expect(root().querySelectorAll('.queue li').length).toBe(1);
  });
  it('aceita lista de códigos com um por linha e permite remover um exemplar', () => {
    clickText('Colar lista');
    input('#batch-pasted', 'EX-1\nEX-2\nEX-3');
    clickText('Adicionar lista de códigos');
    expect(root().querySelectorAll('.queue li').length).toBe(3);
    root().querySelector<HTMLButtonElement>('.remove')!.click();
    fixture.detectChanges();
    expect(root().querySelectorAll('.queue li').length).toBe(2);
  });
  it('recusa geração com quantidade inválida', () => {
    generate(0);
    expect(root().textContent).toContain('Escolha de 1 a 100');
    expect(root().querySelector('.queue')).toBeNull();
  });
  it('exige preço para exemplares comerciais e aplica preço por unidade', () => {
    generate(2);
    input('#batch-destination', 'COMMERCIAL', 'change');
    submit();
    expect(copies.createBatch).not.toHaveBeenCalled();
    input('#batch-price', '39.90');
    submit();
    expect(
      copies.createBatch.calls.mostRecent().args[0].every((copy) => copy.salePrice === 39.9),
    ).toBeTrue();
  });
  it('preserva códigos e dados após conflito e permite corrigir', () => {
    copies.createBatch.and.returnValue(throwError(() => ({ status: 409, detail: 'Duplicado.' })));
    generate(2);
    input('#batch-condition', 'Bom estado');
    submit();
    expect(root().textContent).toContain('Nenhum exemplar foi adicionado');
    expect(root().querySelectorAll('.queue li').length).toBe(2);
    expect(root().querySelector<HTMLInputElement>('#batch-condition')!.value).toBe('Bom estado');
    expect(root().querySelector<HTMLInputElement>('#batch-condition')!.disabled).toBeFalse();
  });
});
