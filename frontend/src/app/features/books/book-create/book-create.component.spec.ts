import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { FormControl, Validators } from '@angular/forms';
import { Router, provideRouter } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../../core/models/auth.model';
import { SnackbarService } from '../../../shared/components/snackbar/snackbar.service';
import { Genre } from '../../catalog/models/catalog.model';
import { CatalogService } from '../../catalog/services/catalog.service';
import { BookResponse } from '../models/book.model';
import { BookService } from '../services/book.service';
import { isbnValidator } from '../validators/isbn.validator';
import { BookCreateComponent } from './book-create.component';

describe('BookCreateComponent', () => {
  let fixture: ComponentFixture<BookCreateComponent>;
  let service: jasmine.SpyObj<BookService>;
  const catalogGenres: Genre[] = [
    { id: 1, name: 'Ficção', slug: 'ficcao' },
    { id: 4, name: 'Fantasia', slug: 'fantasia' },
    { id: 7, name: 'Romance', slug: 'romance' },
  ];

  const response: BookResponse = {
    id: 7,
    isbn: '9788575225530',
    title: 'Python Fluente',
    author: 'Luciano Ramalho',
    genre: 'Tecnologia',
    cover_url: null,
    is_active: true,
    initial_copy: {
      id: 8,
      book_id: 7,
      barcode: 'EX-0001',
      destination: 'DIDACTIC',
      status: 'AVAILABLE',
      condition: null,
      sale_price: null,
      acquired_at: null,
      is_active: true,
    },
  };

  beforeEach(async () => {
    service = jasmine.createSpyObj<BookService>('BookService', ['create', 'lookupMetadata']);
    service.lookupMetadata.and.returnValue(of({
      isbn: '9788575225530',
      title: 'Python Fluente',
      author: 'Luciano Ramalho',
      genre: 'Tecnologia',
    }));
    const catalog = jasmine.createSpyObj<CatalogService>('CatalogService', ['getAllGenres']);
    catalog.getAllGenres.and.returnValue(of(catalogGenres));
    await TestBed.configureTestingModule({
      imports: [BookCreateComponent],
      providers: [
        provideRouter([]),
        { provide: BookService, useValue: service },
        { provide: CatalogService, useValue: catalog },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(BookCreateComponent);
    fixture.detectChanges();
  });

  function input(id: string, value: string): HTMLInputElement {
    const element = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(`#${id}`)!;
    element.value = value;
    element.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    return element;
  }

  function submit(): void {
    const isbn = fixture.componentInstance['form'].controls.isbn.value;
    const barcode = fixture.componentInstance['form'].controls.barcode.value;
    if (isbn && !barcode) {
      input('book-barcode', 'EX-0001');
    }
    const form = (fixture.nativeElement as HTMLElement).querySelector<HTMLFormElement>('form')!;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  function fail(error: ApiError): Observable<never> {
    return throwError(() => error);
  }

  it('cria o componente', () => expect(fixture.componentInstance).toBeTruthy());

  it('exige ISBN e não chama a API sem ele', () => {
    submit();
    expect(service.create).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Informe o ISBN.');
  });

  it('rejeita ISBN com formato ou checksum inválido', () => {
    input('book-isbn', '978-85-7522-553-1');
    submit();
    expect(service.create).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('checksum correto');
  });

  it('aceita ISBN-10 válido', () => {
    const control = new FormControl('0-306-40615-2', [Validators.required, isbnValidator]);
    expect(control.valid).toBeTrue();
  });

  it('aceita ISBN-13 válido', () => {
    const control = new FormControl('978 85 7522 553 0', [Validators.required, isbnValidator]);
    expect(control.valid).toBeTrue();
  });

  it('consulta e preenche apenas campos vazios, sem bloquear a edição', fakeAsync(() => {
    input('book-isbn', '978-85-7522-553-0');
    tick(451);
    fixture.detectChanges();

    expect(service.lookupMetadata).toHaveBeenCalledOnceWith('9788575225530');
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector<HTMLInputElement>('#book-title')?.value).toBe('Python Fluente');
    expect(root.querySelector<HTMLInputElement>('#book-title')?.disabled).toBeFalse();
    expect(root.querySelector<HTMLInputElement>('#book-title')?.readOnly).toBeFalse();
    expect(root.textContent).toContain('Sugestão do Google Books aplicada em campos vazios');
  }));

  it('não sobrescreve título e autor já digitados com a sugestão externa (Issue #176)', fakeAsync(() => {
    input('book-title', 'Título do funcionário');
    input('book-author', 'Autor do funcionário');
    input('book-isbn', '978-85-7522-553-0');
    tick(451);
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector<HTMLInputElement>('#book-title')?.value).toBe('Título do funcionário');
    expect(root.querySelector<HTMLInputElement>('#book-author')?.value).toBe('Autor do funcionário');
    expect(root.textContent).toContain('dados informados foram mantidos');
  }));

  it('não usa a categoria do Google Books como categoria da obra (Issue #176)', fakeAsync(() => {
    spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    service.create.and.returnValue(of(response));
    input('book-isbn', '978-85-7522-553-0');
    tick(451);
    fixture.detectChanges();
    submit();
    expect(service.create.calls.mostRecent().args[0].genre_ids).toEqual([]);
  }));

  it('libera o preenchimento manual quando a consulta falha', fakeAsync(() => {
    service.lookupMetadata.and.returnValue(
      throwError(() => ({ status: 503, detail: 'Serviço indisponível.' })),
    );
    input('book-isbn', '9788575225530');
    tick(451);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#book-title')?.disabled).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('Preencha título e autor manualmente');
  }));

  it('aplica os limites de título e autor', () => {
    input('book-isbn', '9788575225530');
    input('book-title', 'T'.repeat(256));
    input('book-author', 'A'.repeat(256));
    submit();
    expect(service.create).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('título pode ter no máximo 255');
    expect(fixture.nativeElement.textContent).toContain('autor pode ter no máximo 255');
  });

  function pick(id: number): void {
    const box = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(`#book-genre-${id}`)!;
    box.click();
    fixture.detectChanges();
  }

  it('oferece as categorias do catálogo para seleção múltipla (Issue #174)', () => {
    const boxes = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll<HTMLInputElement>('input[type="checkbox"]'));
    expect(boxes.map((box) => box.id)).toEqual(['book-genre-1', 'book-genre-4', 'book-genre-7']);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Fantasia');
    expect((fixture.nativeElement as HTMLElement).querySelector('#book-genre[type="text"]')).toBeNull();
  });

  it('envia as categorias escolhidas em genre_ids, sem usar o texto de gênero', () => {
    service.create.and.returnValue(of(response));
    input('book-isbn', '9788575225530');
    pick(4);
    pick(7);
    pick(4);
    submit();
    const payload = service.create.calls.mostRecent().args[0];
    expect(payload.genre_ids).toEqual([7]);
    expect(payload.genre).toBeUndefined();
  });

  it('envia payload normalizado quando o formulário é válido', () => {
    service.create.and.returnValue(of(response));
    input('book-isbn', ' 978-85-7522-553-0 ');
    input('book-title', '  Python Fluente  ');
    input('book-author', ' Luciano Ramalho ');
    pick(1);
    submit();
    expect(service.create).toHaveBeenCalledOnceWith({
      isbn: '9788575225530',
      title: 'Python Fluente',
      author: 'Luciano Ramalho',
      genre_ids: [1],
      cover_url: null,
      initial_copy: {
        barcode: 'EX-0001', destination: 'DIDACTIC', condition: null,
        sale_price: null, acquired_at: null,
      },
    });
  });

  it('converte campos opcionais vazios em null', () => {
    service.create.and.returnValue(of(response));
    input('book-isbn', '9788575225530');
    input('book-title', '   ');
    submit();
    expect(service.create).toHaveBeenCalledOnceWith({
      isbn: '9788575225530', title: null, author: null, genre_ids: [], cover_url: null,
      initial_copy: {
        barcode: 'EX-0001', destination: 'DIDACTIC', condition: null,
        sale_price: null, acquired_at: null,
      },
    });
  });

  it('bloqueia o botão e impede envio duplo durante a requisição', () => {
    const pending = new Subject<BookResponse>();
    service.create.and.returnValue(pending);
    input('book-isbn', '9788575225530');
    submit();
    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      'button[type="submit"]',
    )!;
    expect(button.disabled).toBeTrue();
    expect(button.textContent).toContain('Cadastrando');
    submit();
    expect(service.create).toHaveBeenCalledTimes(1);
  });

  it('após o 201 avisa o sucesso e abre o detalhe da obra no balcão', () => {
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    const snackbar = spyOn(TestBed.inject(SnackbarService), 'show');
    service.create.and.returnValue(of(response));
    input('book-isbn', '9788575225530');
    submit();
    expect(navigate).toHaveBeenCalledOnceWith(['/balcao/acervo', response.id]);
    expect(snackbar).toHaveBeenCalledOnceWith('Obra “Python Fluente” cadastrada com sucesso.', 'success');
  });

  it('não navega nem avisa sucesso quando o backend recusa o cadastro', () => {
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    const snackbar = spyOn(TestBed.inject(SnackbarService), 'show');
    service.create.and.returnValue(throwError(() => ({ status: 409, code: 'duplicate_isbn', detail: 'ISBN já cadastrado.' } as ApiError)));
    input('book-isbn', '9788575225530');
    submit();
    expect(navigate).not.toHaveBeenCalled();
    expect(snackbar).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('ISBN já cadastrado.');
  });

  it('oferece o retorno ao acervo do balcão', () => {
    expect((fixture.nativeElement as HTMLElement).querySelector('a.back')?.getAttribute('href')).toBe('/balcao/acervo');
  });

  [
    {
      name: '403',
      error: {
        status: 403,
        code: 'permission_denied',
        detail: 'Você não tem permissão para realizar esta ação.',
      },
    },
    {
      name: 'ISBN não encontrado',
      error: {
        status: 404,
        code: 'google_books_not_found',
        detail: 'O ISBN não foi encontrado no Google Books.',
      },
    },
    {
      name: 'ISBN duplicado',
      error: { status: 409, code: 'duplicate_isbn', detail: 'Este ISBN já está cadastrado.' },
    },
    {
      name: 'código de barras duplicado',
      error: { status: 409, code: 'duplicate_barcode', detail: 'Este código de barras já está cadastrado.' },
    },
    {
      name: 'indisponibilidade externa',
      error: {
        status: 503,
        code: 'google_books_unavailable',
        detail: 'Não foi possível consultar os dados externos. Tente novamente em instantes.',
      },
    },
    {
      name: 'resposta externa inválida',
      error: {
        status: 502,
        code: 'google_books_invalid_response',
        detail: 'O Google Books não retornou título e autor válidos para este ISBN.',
      },
    },
    {
      name: 'falha inesperada',
      error: {
        status: 500,
        detail: 'Tivemos um problema no servidor. Tente novamente em instantes.',
      },
    },
  ].forEach(({ name, error }) => {
    it(`trata ${name} sem expor resposta técnica`, () => {
      service.create.and.returnValue(fail(error));
      input('book-isbn', '9788575225530');
      submit();
      expect(fixture.nativeElement.textContent).toContain(error.detail);
    });
  });

  it('associa uma resposta 422 ao campo indicado pelo backend', () => {
    service.create.and.returnValue(
      fail({
        status: 422,
        detail: 'Confira os dados informados e tente novamente.',
        validationErrors: [{ field: 'isbn', message: 'Value error' }],
      }),
    );
    input('book-isbn', '9788575225530');
    submit();
    expect(fixture.nativeElement.textContent).toContain('O backend rejeitou este ISBN');
    expect(fixture.nativeElement.textContent).toContain('Confira os campos destacados');
  });

  it('preserva os dados digitados depois de um erro', () => {
    service.create.and.returnValue(fail({ status: 0, detail: 'Sem conexão.' }));
    input('book-isbn', '9788575225530');
    input('book-title', 'Meu título');
    submit();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector<HTMLInputElement>('#book-isbn')?.value).toBe('9788575225530');
    expect(root.querySelector<HTMLInputElement>('#book-title')?.value).toBe('Meu título');
  });

  it('exige os dados do exemplar inicial', () => {
    input('book-isbn', '9788575225530');
    const form = (fixture.nativeElement as HTMLElement).querySelector<HTMLFormElement>('form')!;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(service.create).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Informe o código de barras');
  });

  it('exige preço para exemplar comercial e o envia no payload combinado', () => {
    input('book-isbn', '9788575225530');
    input('book-barcode', 'COM-1');
    const root = fixture.nativeElement as HTMLElement;
    const destination = root.querySelector<HTMLSelectElement>('#book-destination')!;
    destination.value = 'COMMERCIAL';
    destination.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    const form = root.querySelector<HTMLFormElement>('form')!;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(service.create).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Informe o preço');
    service.create.and.returnValue(of(response));
    input('book-sale-price', '49.9');
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(service.create.calls.mostRecent().args[0].initial_copy.sale_price).toBe(49.9);
  });

  it('rejeita preço zero do exemplar comercial na inclusão da obra (Issue #175)', () => {
    input('book-isbn', '9788575225530');
    input('book-barcode', 'COM-0');
    const root = fixture.nativeElement as HTMLElement;
    const destination = root.querySelector<HTMLSelectElement>('#book-destination')!;
    destination.value = 'COMMERCIAL';
    destination.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    input('book-sale-price', '0');
    root.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(service.create).not.toHaveBeenCalled();
    expect(root.textContent).toContain('O preço de venda deve ser maior que zero.');
  });

  it('mostra a mensagem do 422 de domínio de preço devolvido pelo backend', () => {
    service.create.and.returnValue(fail({
      status: 422, code: 'copy_sale_price_required',
      detail: 'Exemplar destinado à venda exige preço de venda maior que zero.',
    }));
    input('book-isbn', '9788575225530');
    submit();
    expect(fixture.nativeElement.textContent).toContain('exige preço de venda maior que zero');
  });

  it('orienta cadastro manual quando a integração retorna 503', () => {
    service.create.and.returnValue(fail({ status: 503, code: 'google_books_rate_limited', detail: 'Serviço indisponível.' }));
    input('book-isbn', '9788575225530');
    submit();
    expect(fixture.nativeElement.textContent).toContain('Preencha título e autor manualmente');
  });
});
