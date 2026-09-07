import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, of, Subject, throwError } from 'rxjs';

import { ApiError } from '../../../core/models/auth.model';
import { CopyResponse } from '../models/copy.model';
import { CopyService } from '../services/copy.service';
import { CopyCreateComponent } from './copy-create.component';

describe('CopyCreateComponent', () => {
  let fixture: ComponentFixture<CopyCreateComponent>;
  let service: jasmine.SpyObj<CopyService>;
  let params: BehaviorSubject<ReturnType<typeof convertToParamMap>>;

  const response: CopyResponse = {
    id: 4, bookId: 8, barcode: 'RET-9', destination: 'COMMERCIAL', condition: 'Novo', salePrice: 25.5, acquiredAt: '2026-09-06', status: 'AVAILABLE', isActive: true,
  };

  beforeEach(async () => {
    service = jasmine.createSpyObj<CopyService>('CopyService', ['create']);
    params = new BehaviorSubject(convertToParamMap({ id: '8' }));
    await TestBed.configureTestingModule({
      imports: [CopyCreateComponent],
      providers: [
        provideRouter([]),
        { provide: CopyService, useValue: service },
        { provide: ActivatedRoute, useValue: { paramMap: params } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CopyCreateComponent);
    fixture.detectChanges();
  });

  function input(id: string, value: string): void {
    const element = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(`#${id}`)!;
    element.value = value;
    element.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function select(value: string): void {
    const element = (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>('#copy-destination')!;
    element.value = value;
    element.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function submit(): void {
    (fixture.nativeElement as HTMLElement).querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  function validCommercial(): void {
    input('copy-barcode', ' RET-9 ');
    select('COMMERCIAL');
    input('copy-salePrice', '25.50');
  }

  it('cria o componente com rota válida', () => expect(fixture.componentInstance).toBeTruthy());

  it('marca rota ausente, não numérica, zero ou negativa como inválida e bloqueia envio', () => {
    for (const id of [null, 'abc', '0', '-1']) {
      params.next(convertToParamMap(id === null ? {} : { id }));
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('identificador da obra é inválido');
    }
    expect(service.create).not.toHaveBeenCalled();
  });

  it('exige código de barras', () => { submit(); expect(fixture.nativeElement.textContent).toContain('Informe o código de barras.'); });
  it('limita código de barras a 100 caracteres', () => { input('copy-barcode', 'A'.repeat(101)); submit(); expect(fixture.nativeElement.textContent).toContain('no máximo 100 caracteres'); });
  it('trima código de barras antes do envio', () => { service.create.and.returnValue(of(response)); validCommercial(); submit(); expect(service.create.calls.mostRecent().args[0].barcode).toBe('RET-9'); });
  it('exige escolha explícita de destinação', () => { input('copy-barcode', 'RET-9'); submit(); expect(fixture.nativeElement.textContent).toContain('Escolha a destinação'); });
  it('limita condição a 30 caracteres', () => { input('copy-condition', 'N'.repeat(31)); submit(); expect(fixture.nativeElement.textContent).toContain('condição pode ter no máximo 30'); });
  it('converte condição vazia em null', () => { service.create.and.returnValue(of(response)); validCommercial(); input('copy-condition', '   '); submit(); expect(service.create.calls.mostRecent().args[0].condition).toBeNull(); });
  it('converte data de aquisição vazia em null', () => { service.create.and.returnValue(of(response)); validCommercial(); submit(); expect(service.create.calls.mostRecent().args[0].acquiredAt).toBeNull(); });
  it('exige preço apenas para destinação comercial', () => { input('copy-barcode', 'RET-9'); select('COMMERCIAL'); submit(); expect(fixture.nativeElement.textContent).toContain('Informe o preço de venda.'); });
  it('rejeita preço com mais de duas casas decimais', () => { input('copy-barcode', 'RET-9'); select('COMMERCIAL'); input('copy-salePrice', '1.999'); submit(); expect(fixture.nativeElement.textContent).toContain('até 10 dígitos e duas casas'); });
  it('rejeita preço com mais de 10 dígitos totais', () => { input('copy-barcode', 'RET-9'); select('COMMERCIAL'); input('copy-salePrice', '1234567890.1'); submit(); expect(fixture.nativeElement.textContent).toContain('até 10 dígitos e duas casas'); });
  it('envia preço nulo para destinação didática', () => { service.create.and.returnValue(of(response)); input('copy-barcode', 'RET-9'); select('DIDACTIC'); input('copy-salePrice', '99.99'); submit(); expect(service.create.calls.mostRecent().args[0].salePrice).toBeNull(); });
  it('bloqueia submit com formulário inválido', () => { submit(); expect(service.create).not.toHaveBeenCalled(); });
  it('impede múltiplos envios durante loading', () => { const pending = new Subject<CopyResponse>(); service.create.and.returnValue(pending); validCommercial(); submit(); submit(); expect(service.create).toHaveBeenCalledTimes(1); });
  it('exibe dados reais devolvidos no 201 e permanece na tela', () => { service.create.and.returnValue(of(response)); validCommercial(); submit(); const text = fixture.nativeElement.textContent; expect(text).toContain('RET-9'); expect(text).toContain('AVAILABLE'); expect(text).toContain('Cadastrar outro exemplar'); });
  it('limpa campos editáveis e mantém bookId ao cadastrar outro exemplar', () => { service.create.and.returnValue(of(response)); validCommercial(); submit(); (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('button[type="button"]')!.click(); fixture.detectChanges(); expect((fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#copy-condition')?.value).toBe(''); validCommercial(); service.create.and.returnValue(of(response)); submit(); expect(service.create.calls.mostRecent().args[0].bookId).toBe(8); });
  it('preserva o formulário e trata 401, 403, 404, 409, 422 e 500', () => {
    const errors: ApiError[] = [
      { status: 401, detail: 'Sua sessão expirou.' }, { status: 403, detail: 'Permissão insuficiente.' },
      { status: 404, detail: 'Não encontrado.' }, { status: 409, detail: 'Duplicado.' },
      { status: 422, detail: 'Inválido.', validationErrors: [{ field: 'barcode', message: 'inválido' }] }, { status: 500, detail: 'Tivemos um problema no servidor.' },
    ];
    for (const error of errors) {
      service.create.and.returnValue(throwError(() => error));
      validCommercial();
      submit();
      expect((fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#copy-barcode')?.value).toContain('RET-9');
    }
  });
});
