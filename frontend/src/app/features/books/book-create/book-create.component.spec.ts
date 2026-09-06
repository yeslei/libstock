import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, Validators } from '@angular/forms';
import { provideRouter } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../../core/models/auth.model';
import { BookResponse } from '../models/book.model';
import { BookService } from '../services/book.service';
import { isbnValidator } from '../validators/isbn.validator';
import { BookCreateComponent } from './book-create.component';

describe('BookCreateComponent', () => {
  let fixture: ComponentFixture<BookCreateComponent>;
  let service: jasmine.SpyObj<BookService>;

  const response: BookResponse = {
    id: 7,
    isbn: '9788575225530',
    title: 'Python Fluente',
    author: 'Luciano Ramalho',
    genre: 'Tecnologia',
  };

  beforeEach(async () => {
    service = jasmine.createSpyObj<BookService>('BookService', ['create']);
    await TestBed.configureTestingModule({
      imports: [BookCreateComponent],
      providers: [provideRouter([]), { provide: BookService, useValue: service }],
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

  it('aplica os limites de título, autor e gênero', () => {
    input('book-isbn', '9788575225530');
    input('book-title', 'T'.repeat(256));
    input('book-author', 'A'.repeat(256));
    input('book-genre', 'G'.repeat(101));
    submit();
    expect(service.create).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('título pode ter no máximo 255');
    expect(fixture.nativeElement.textContent).toContain('autor pode ter no máximo 255');
    expect(fixture.nativeElement.textContent).toContain('gênero pode ter no máximo 100');
  });

  it('envia payload normalizado quando o formulário é válido', () => {
    service.create.and.returnValue(of(response));
    input('book-isbn', ' 978-85-7522-553-0 ');
    input('book-title', '  Python Fluente  ');
    input('book-author', ' Luciano Ramalho ');
    input('book-genre', ' Tecnologia ');
    submit();
    expect(service.create).toHaveBeenCalledOnceWith({
      isbn: '9788575225530',
      title: 'Python Fluente',
      author: 'Luciano Ramalho',
      genre: 'Tecnologia',
    });
  });

  it('converte campos opcionais vazios em null', () => {
    service.create.and.returnValue(of(response));
    input('book-isbn', '9788575225530');
    input('book-title', '   ');
    submit();
    expect(service.create).toHaveBeenCalledOnceWith({
      isbn: '9788575225530', title: null, author: null, genre: null,
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

  it('exibe os dados efetivamente devolvidos no 201', () => {
    service.create.and.returnValue(of(response));
    input('book-isbn', '9788575225530');
    submit();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Obra cadastrada com sucesso.');
    expect(text).toContain(response.isbn);
    expect(text).toContain(response.title);
    expect(text).toContain(response.author);
    expect(text).toContain(response.genre);
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
});
