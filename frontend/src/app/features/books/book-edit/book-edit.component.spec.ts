import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { BookDetail } from '../models/book.model';
import { BookService } from '../services/book.service';
import { BookEditComponent } from './book-edit.component';

describe('BookEditComponent', () => {
  let fixture: ComponentFixture<BookEditComponent>;
  let service: jasmine.SpyObj<BookService>;
  const book: BookDetail = { id: 5, isbn: '9788575225530', title: 'Obra', author: 'Autora', genre: null, cover_url: 'https://img.example/capa.jpg', is_active: true, initial_copy: null, copies: [] };

  beforeEach(async () => {
    service = jasmine.createSpyObj('BookService', ['get', 'update']);
    service.get.and.returnValue(of(book));
    await TestBed.configureTestingModule({
      imports: [BookEditComponent],
      providers: [provideRouter([]), { provide: BookService, useValue: service }, { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: '5' }) } } }],
    }).compileComponents();
    fixture = TestBed.createComponent(BookEditComponent);
    fixture.detectChanges();
  });

  it('carrega e atualiza obra incluindo a URL da capa', () => {
    service.update.and.returnValue(of({ ...book, title: 'Obra atualizada' }));
    const title = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#edit-title')!;
    title.value = 'Obra atualizada'; title.dispatchEvent(new Event('input'));
    (fixture.nativeElement as HTMLElement).querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(service.update).toHaveBeenCalledWith(5, jasmine.objectContaining({ title: 'Obra atualizada', cover_url: book.cover_url }));
    expect(fixture.nativeElement.textContent).toContain('Obra atualizada com sucesso');
  });

  it('preserva os campos quando a persistência falha', () => {
    service.update.and.returnValue(throwError(() => ({ status: 500, detail: 'Falha ao salvar.' })));
    const title = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#edit-title')!;
    title.value = 'Texto preservado'; title.dispatchEvent(new Event('input'));
    (fixture.nativeElement as HTMLElement).querySelector('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(title.value).toBe('Texto preservado');
    expect(fixture.nativeElement.textContent).toContain('Falha ao salvar');
  });
});
