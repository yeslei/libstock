import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
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
  it('oferece a reimpressão do comprovante só para empréstimos já registrados (ativos e em atraso)', async () => {
    const base = { book_id: 42, author: 'A', cover_url: null, copy_barcode: '1', due_date: '2026-11-01', pickup_date: '2026-10-01', days_late: 0 };
    const { root } = await render('loans', [{ ...base, id: 7, title: 'Ativo', status: 'ACTIVE' }, { ...base, id: 8, title: 'Atrasado', status: 'OVERDUE', days_late: 2 }, { ...base, id: 9, title: 'Pedido', status: 'AWAITING_PICKUP' }]);
    const hrefs = Array.from(root.querySelectorAll('a')).filter((a) => a.textContent?.trim() === 'Ver comprovante').map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/comprovantes/emprestimo/7', '/comprovantes/emprestimo/8']);
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

  describe("cancelamento de reserva (Issue #150)", () => {
    const waiting = { id: 1, book_id: 42, title: "Sapiens", author: "Autor", cover_url: null, status: "WAITING", queue_position: 2 };
    const notified = { id: 2, book_id: 43, title: "Livro", author: "Autor", cover_url: null, status: "NOTIFIED", copy_barcode: "0032", available_since: "2026-10-03T12:00:00Z", expires_at: "2026-10-09T02:59:59.999Z", expired: false };
    async function renderReservations(items: any[], cancel: any) {
      const service = { getLoans: () => of([]), getReservations: jasmine.createSpy().and.returnValue(of(items)), cancelReservation: cancel };
      await TestBed.configureTestingModule({ imports: [ClientTrackingComponent], providers: [provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { data: { tracking: "reservations" } } } },
        { provide: ClientTrackingService, useValue: service }] }).compileComponents();
      const fixture = TestBed.createComponent(ClientTrackingComponent); fixture.detectChanges();
      const root = fixture.nativeElement as HTMLElement;
      const click = (el: Element | null) => { (el as HTMLElement).click(); fixture.detectChanges(); };
      const cancelButton = (n = 0) => root.querySelectorAll("button.cancel")[n];
      return { fixture, service, root, click, cancelButton };
    }

    it("mostra o prazo real e cancela somente após confirmar, sem envio duplo, com sucesso após o 2xx", async () => {
      const response = new Subject<{ id: number }>();
      const { root, service, click, cancelButton, fixture } = await renderReservations([notified], jasmine.createSpy().and.returnValue(response));
      expect(root.textContent).toContain("Retire até 08/10/2026");
      click(cancelButton());
      expect(service.cancelReservation).not.toHaveBeenCalled();
      expect(root.querySelector("dialog")!.textContent).toContain("O exemplar destinado a você será liberado");
      const submit = root.querySelector("dialog .confirm__submit");
      click(submit); click(submit);
      expect(service.cancelReservation).toHaveBeenCalledOnceWith(2);
      expect(snackbarMessage()).toBe("");
      response.next({ id: 2 }); response.complete(); fixture.detectChanges();
      expect(snackbarMessage()).toBe("Reserva cancelada.");
      expect(snackbarVariant()).toBe("success");
      expect(service.getReservations).toHaveBeenCalledTimes(2);
    });

    it("cancelar a reserva aguardando pede confirmação e permite desistir", async () => {
      const { root, service, click, cancelButton } = await renderReservations([waiting], jasmine.createSpy());
      click(cancelButton());
      expect(root.querySelector("dialog")!.textContent).toContain("Você sairá da fila de compra");
      click(root.querySelector("dialog .confirm__cancel"));
      expect(root.querySelector("dialog")).toBeNull();
      expect(service.cancelReservation).not.toHaveBeenCalled();
    });

    it("mostra a recusa de estado final sem sucesso e recarrega a lista", async () => {
      const cancel = jasmine.createSpy().and.returnValue(throwError(() => ({ detail: "Esta reserva já foi encerrada e não pode ser cancelada.", code: "reservation_not_cancellable", status: 409 })));
      const { service, click, cancelButton, root } = await renderReservations([waiting], cancel);
      click(cancelButton());
      click(root.querySelector("dialog .confirm__submit"));
      expect(snackbarMessage()).toContain("já foi encerrada");
      expect(snackbarVariant()).toBe("warning");
      expect(service.getReservations).toHaveBeenCalledTimes(2);
    });

    it("reserva destinada vencida informa o encerramento e não oferece cancelar", async () => {
      const { root, cancelButton } = await renderReservations([{ ...notified, expired: true }], jasmine.createSpy());
      expect(root.textContent).toContain("Prazo de retirada encerrado em 08/10/2026");
      expect(root.textContent).toContain("O prazo de retirada terminou");
      expect(cancelButton()).toBeUndefined();
    });
  });
});
