import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ClientTrackingComponent } from './client-tracking.component';
import { ClientTrackingService } from './client-tracking.service';

describe('Acompanhamento do cliente', () => {
  async function render(tracking: string, items: any[] = [], fails = false) {
    const service = { getLoans: jasmine.createSpy().and.returnValue(fails ? throwError(() => new Error()) : of(items)), getReservations: jasmine.createSpy().and.returnValue(of(items)) };
    await TestBed.configureTestingModule({ imports: [ClientTrackingComponent], providers: [provideRouter([]),
      { provide: ActivatedRoute, useValue: { snapshot: { data: { tracking } } } },
      { provide: ClientTrackingService, useValue: service },
    ] }).compileComponents();
    const fixture = TestBed.createComponent(ClientTrackingComponent); fixture.detectChanges();
    return { fixture, service, root: fixture.nativeElement as HTMLElement };
  }
  it('mostra o aviso quando ainda não existem empréstimos', async () => {
    const { root, service } = await render('loans');
    expect(root.textContent).toContain('Você não possui empréstimos ou solicitações em andamento.');
    expect(service.getLoans).toHaveBeenCalledTimes(1);
    expect(root.querySelector('article')).toBeNull();
  });
  it('mostra o aviso quando não existem reservas de compra', async () => {
    const { root } = await render('reservations');
    expect(root.textContent).toContain('Você não possui reservas de compra em andamento.');
  });
  it('mostra atraso, exemplar e orientação sem ações de funcionário', async () => {
    const { root } = await render('loans', [{ id:1,book_id:42,title:'1984',author:'George Orwell',cover_url:null,status:'OVERDUE',copy_barcode:'00402',due_date:'2026-09-15',pickup_date:'2026-08-15',days_late:5 }]);
    expect(root.textContent).toContain('Em atraso');
    expect(root.textContent).toContain('vencido há 5 dias');
    expect(root.textContent).toContain('Este atraso gera pendência');
    expect(root.querySelector('button')).toBeNull();
  });
  it('mostra a posição retornada e o prazo apenas quando existe', async () => {
    const { root } = await render('reservations', [{id:1,book_id:42,title:'Sapiens',author:'Autor',cover_url:null,status:'WAITING',queue_position:2},
      {id:2,book_id:43,title:'Livro',author:'Autor',cover_url:null,status:'NOTIFIED',copy_barcode:'0032',available_since:'2026-10-03T12:00:00Z',expires_at:null}]);
    expect(root.textContent).toContain('2º lugar');
    expect(root.textContent).toContain('Disponível para retirada');
    expect(root.textContent).not.toContain('Retire até');
  });
  it('distingue falha de consulta da ausência de empréstimos', async () => {
    const { root } = await render('loans', [], true);
    expect(root.textContent).toContain('Tentar novamente');
    expect(root.textContent).not.toContain('Você não possui empréstimos');
  });
  it('mostra o prazo de retirada somente quando expires_at foi persistido', async () => {
    const { root } = await render('reservations', [{id:2,book_id:43,title:'Livro',author:'Autor',cover_url:null,status:'NOTIFIED',copy_barcode:'0032',available_since:'2026-09-20T12:00:00Z',expires_at:'2026-09-23T12:00:00Z'}]);
    expect(root.textContent).toContain('Exemplar #0032');
    expect(root.textContent).toContain('Disponível desde 20/09/2026');
    expect(root.textContent).toContain('Retire até 23/09/2026');
    expect(root.textContent).toContain('Dirija-se ao balcão até 23/09/2026 para finalizar a compra.');
    expect(root.textContent).toContain('Compras concluídas não aparecem aqui.');
  });
  it('sem expires_at orienta ir ao balcão sem inventar prazo', async () => {
    const { root } = await render('reservations', [{id:2,book_id:43,title:'Livro',author:'Autor',cover_url:null,status:'NOTIFIED',copy_barcode:null,available_since:'2026-09-20T12:00:00Z',expires_at:null}]);
    expect(root.textContent).toContain('Exemplar aguardando identificação no balcão');
    expect(root.textContent).toContain('Dirija-se ao balcão para finalizar a compra.');
    expect(root.textContent).not.toMatch(/até d/);
  });
  it('mostra solicitação aguardando retirada, empréstimo ativo e um dia de atraso no singular', async () => {
    const { root } = await render('loans', [
      {id:1,book_id:1,title:'Dom Casmurro',author:'Machado de Assis',cover_url:null,status:'AWAITING_PICKUP',pickup_date:'2026-09-20'},
      {id:2,book_id:2,title:'Sapiens',author:'Harari',cover_url:null,status:'ACTIVE',copy_barcode:'00204',pickup_date:'2026-09-10',due_date:'2026-10-10'},
      {id:3,book_id:3,title:'1984',author:'Orwell',cover_url:null,status:'OVERDUE',copy_barcode:'00402',pickup_date:'2026-08-15',due_date:'2026-09-15',days_late:1}]);
    expect(root.textContent).toContain('Aguardando retirada');
    expect(root.textContent).toContain('Retirada solicitada para 20/09/2026.');
    expect(root.textContent).toContain('Apresente seu e-mail cadastrado no balcão');
    expect(root.textContent).toContain('Empréstimo ativo');
    expect(root.textContent).toContain('Devolução prevista: 10/10/2026');
    expect(root.textContent).toContain('vencido há 1 dia.');
    expect(root.querySelectorAll('article').length).toBe(3);
    expect(root.querySelector('.status--overdue')!.textContent).toContain('Em atraso');
  });
  it('tenta novamente após falha e mostra os dados sem falso vazio', async () => {
    const getLoans = jasmine.createSpy().and.returnValues(throwError(() => new Error()), of([{id:1,book_id:1,title:'Dom Casmurro',author:'M',cover_url:null,status:'AWAITING_PICKUP',pickup_date:'2026-09-20'}]));
    await TestBed.configureTestingModule({ imports: [ClientTrackingComponent], providers: [provideRouter([]),
      { provide: ActivatedRoute, useValue: { snapshot: { data: { tracking: 'loans' } } } },
      { provide: ClientTrackingService, useValue: { getLoans, getReservations: () => of([]) } }] }).compileComponents();
    const fixture = TestBed.createComponent(ClientTrackingComponent); fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Não foi possível carregar seu acompanhamento.');
    (root.querySelector('button') as HTMLButtonElement).click(); fixture.detectChanges();
    expect(getLoans).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain('Dom Casmurro');
    expect(root.textContent).not.toContain('Tentar novamente');
  });
});
