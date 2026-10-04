import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';

import { RoleCode } from '../../core/models/user.model';
import { TokenStoreService } from '../../core/services/token-store.service';
import { CounterCatalogComponent } from './counter-catalog.component';
import { CounterService, StaffCatalogBook } from './counter.service';

const book = (over: Partial<StaffCatalogBook> = {}): StaffCatalogBook => ({
  id: 7, title: 'Dom Casmurro', author: 'Machado de Assis', isbn: '9780000000002', genre: 'Romance',
  is_active: true, total_copies: 4, didactic_copies: 3, commercial_copies: 1, ...over,
});

function setup(configure: (service: jasmine.SpyObj<CounterService>) => void, roles: RoleCode[] = ['SELLER']) {
  const service = jasmine.createSpyObj<CounterService>('CounterService', ['listCatalogBooks']);
  configure(service);
  TestBed.configureTestingModule({
    imports: [CounterCatalogComponent],
    providers: [provideRouter([]), { provide: CounterService, useValue: service }],
  });
  TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: roles, created_at: '' });
  const fixture = TestBed.createComponent(CounterCatalogComponent);
  fixture.detectChanges();
  return { fixture, service, root: fixture.nativeElement as HTMLElement };
}

function search(fixture: ComponentFixture<unknown>, root: HTMLElement, term: string) {
  const input = root.querySelector('#catalog-q') as HTMLInputElement;
  input.value = term; input.dispatchEvent(new Event('input'));
  root.querySelector('form')!.dispatchEvent(new Event('submit'));
  fixture.detectChanges();
}

describe('Balcão: acervo', () => {
  it('segue o frame: título, busca por título, autor ou ISBN e colunas da tabela', () => {
    const { root } = setup((s) => s.listCatalogBooks.and.returnValue(of([book()])));
    expect(root.querySelector('h1')?.textContent).toBe('Acervo');
    expect(root.textContent).toContain('FUNCIONÁRIO · ACERVO');
    expect(root.textContent).toContain('Obras cadastradas');
    expect((root.querySelector('#catalog-q') as HTMLInputElement).placeholder).toBe('Buscar por título, autor ou ISBN');
    expect(Array.from(root.querySelectorAll('th')).map((th) => th.textContent?.trim())).toEqual(
      ['Obra / título', 'Autor', 'Categoria', 'Exemplares', 'Ações']);
    const row = root.querySelector('tbody tr')!;
    expect(row.textContent).toContain('Dom Casmurro');
    expect(row.textContent).toContain('Obra cadastrada');
    expect(row.textContent).toContain('Machado de Assis');
    expect(row.querySelector('.badge')?.textContent).toBe('Romance');
    expect(row.querySelector('.pill')?.textContent).toBe('4 cópias');
    expect(row.querySelector('a')?.getAttribute('href')).toBe('/balcao/acervo/7');
  });

  it('usa singular para uma cópia e sinaliza obra inativa sem categoria', () => {
    const { root } = setup((s) => s.listCatalogBooks.and.returnValue(of([book({ total_copies: 1, is_active: false, genre: null })])));
    const row = root.querySelector('tbody tr')!;
    expect(row.querySelector('.pill')?.textContent).toBe('1 cópia');
    expect(row.textContent).toContain('Obra inativa');
    expect(row.querySelector('.badge')).toBeNull();
  });

  it('mostra carregamento e depois o vazio', () => {
    const pending = new Subject<StaffCatalogBook[]>();
    const { fixture, root } = setup((s) => s.listCatalogBooks.and.returnValue(pending));
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Carregando');
    pending.next([]);
    fixture.detectChanges();
    expect(root.textContent).toContain('Nenhuma obra encontrada.');
  });

  it('diferencia erro de lista vazia e permite tentar de novo', () => {
    const { fixture, root, service } = setup((s) =>
      s.listCatalogBooks.and.returnValue(throwError(() => ({ detail: 'Cadastro de funcionário ativo necessário.' }))));
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Cadastro de funcionário ativo necessário.');
    expect(root.textContent).not.toContain('Nenhuma obra');
    service.listCatalogBooks.and.returnValue(of([book()]));
    (Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Tentar novamente') as HTMLElement).click();
    fixture.detectChanges();
    expect(root.querySelector('tbody tr')).not.toBeNull();
  });

  it('busca pelo termo informado', () => {
    const { fixture, root, service } = setup((s) => s.listCatalogBooks.and.returnValue(of([])));
    search(fixture, root, ' orwell ');
    expect(service.listCatalogBooks.calls.mostRecent().args[0]).toBe(' orwell ');
    expect(service.listCatalogBooks).toHaveBeenCalledTimes(2);
  });

  it('avisa quando a lista atinge o limite', () => {
    const many = Array.from({ length: 50 }, (_, i) => book({ id: i + 1 }));
    const { root } = setup((s) => s.listCatalogBooks.and.returnValue(of(many)));
    expect(root.textContent).toContain('Mostrando as primeiras 50 obras');
  });

  it('oferece "+ Nova obra" apenas ao administrador', () => {
    const seller = setup((s) => s.listCatalogBooks.and.returnValue(of([])));
    expect(seller.root.textContent).not.toContain('+ Nova obra');
    TestBed.resetTestingModule();
    const admin = setup((s) => s.listCatalogBooks.and.returnValue(of([])), ['ADMINISTRATOR']);
    const link = Array.from(admin.root.querySelectorAll('a')).find((a) => a.textContent?.trim() === '+ Nova obra');
    expect(link?.getAttribute('href')).toBe('/obras/nova');
  });
});
