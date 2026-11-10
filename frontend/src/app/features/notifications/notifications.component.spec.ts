import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { ClientNotification, NotificationPage, NotificationService } from './notification.service';
import { NotificationsComponent } from './notifications.component';

function item(overrides: Partial<ClientNotification> = {}): ClientNotification {
  return { id: 10, reservation_id: 3, type: 'RESERVATION_AVAILABLE', channel: 'IN_APP', subject: 'Reserva disponível',
    message: 'Dom Casmurro está disponível para retirada.', status: 'SENT', created_at: '2026-11-09T15:00:00Z',
    sent_at: '2026-11-09T15:00:00Z', read_at: null, ...overrides };
}

describe('Caixa de notificações', () => {
  async function setup(page: NotificationPage = { items: [item()], next_before_id: null }) {
    const api = jasmine.createSpyObj<NotificationService>('NotificationService', ['list', 'markRead']);
    api.list.and.returnValue(of(page));
    api.markRead.and.returnValue(of(item({ status: 'READ', read_at: '2026-11-09T15:01:00Z' })));
    TestBed.configureTestingModule({ imports: [NotificationsComponent], providers: [provideRouter([]), { provide: NotificationService, useValue: api }] });
    const fixture = TestBed.createComponent(NotificationsComponent);
    fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    function click(label: string) {
      const button = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find((b) => b.textContent?.trim() === label)!;
      expect(button).withContext(label).toBeTruthy(); button.click(); fixture.detectChanges();
    }
    return { api, fixture, root, click };
  }

  it('distingue canais e estados e só oferece leitura para mensagens entregues', async () => {
    const ctx = await setup({ items: [item(), item({ id: 9, channel: 'EMAIL', status: 'PENDING', sent_at: null }),
      item({ id: 8, channel: 'EMAIL', status: 'SENT' }), item({ id: 7, channel: 'EMAIL', status: 'FAILED', sent_at: null }),
      item({ id: 6, status: 'READ', read_at: '2026-11-09T15:01:00Z' })], next_before_id: null });
    expect(Array.from(ctx.root.querySelectorAll('.status')).map((node) => node.textContent?.trim())).toEqual([
      'Não lida', 'Aguardando envio', 'Enviado', 'Envio não confirmado', 'Lida',
    ]);
    expect(ctx.root.querySelectorAll('.notification button').length).toBe(2);
    expect(ctx.root.textContent).toContain('A entrega na caixa postal depende');
    expect(ctx.api.markRead).not.toHaveBeenCalled();
    expect(ctx.root.querySelector('a[href="/perfil"]')).not.toBeNull();
    expect(ctx.root.querySelector('a[href="/minhas-reservas"]')).not.toBeNull();
  });

  it('lista vazia e recuperação de falha de consulta não simulam mensagens', async () => {
    const ctx = await setup({ items: [], next_before_id: null });
    expect(ctx.root.textContent).toContain('Você ainda não possui notificações.');
    ctx.api.list.and.returnValue(throwError(() => ({ status: 500 })));
    (ctx.fixture.componentInstance as any).load(); ctx.fixture.detectChanges();
    expect(ctx.root.textContent).toContain('Não foi possível consultar');
    expect(ctx.root.querySelector('.notification-list')).toBeNull();
    ctx.api.list.and.returnValue(of({ items: [item()], next_before_id: null }));
    ctx.click('Atualizar consulta');
    expect(ctx.root.querySelectorAll('.notification').length).toBe(1);
  });

  it('carrega a próxima página pelo cursor sem substituir a página anterior', async () => {
    const ctx = await setup({ items: [item()], next_before_id: 10 });
    ctx.api.list.and.returnValue(of({ items: [item({ id: 9 })], next_before_id: null }));
    ctx.click('Carregar mais');
    expect(ctx.api.list).toHaveBeenCalledWith(10);
    expect(ctx.root.querySelectorAll('.notification').length).toBe(2);
    expect(ctx.root.textContent).not.toContain('Carregar mais');
  });

  it('aguarda confirmação da leitura e impede envios duplicados', async () => {
    const ctx = await setup();
    const response = new Subject<ClientNotification>();
    ctx.api.markRead.and.returnValue(response);
    ctx.click('Marcar como lida');
    expect(ctx.api.markRead).toHaveBeenCalledOnceWith(10);
    expect(ctx.root.textContent).not.toContain('Notificação marcada como lida.');
    expect(ctx.root.querySelector<HTMLButtonElement>('.notification button')?.disabled).toBeTrue();
    ctx.root.querySelector<HTMLButtonElement>('.notification button')?.click();
    expect(ctx.api.markRead).toHaveBeenCalledTimes(1);
    response.next(item({ status: 'READ', read_at: '2026-11-09T15:01:00Z' })); response.complete(); ctx.fixture.detectChanges();
    expect(ctx.root.textContent).toContain('Notificação marcada como lida.');
    expect(ctx.root.querySelector('.notification button')).toBeNull();
  });

  for (const status of [0, 500]) {
    it(`reconcilia resultado incerto (${status}) por GET desde a primeira página`, async () => {
      const ctx = await setup({ items: [item()], next_before_id: 10 });
      ctx.api.markRead.and.returnValue(throwError(() => ({ status })));
      ctx.click('Marcar como lida');
      expect(ctx.root.textContent).toContain('Não foi possível confirmar o resultado');
      expect(ctx.root.querySelector<HTMLButtonElement>('.notification button')?.disabled).toBeTrue();
      ctx.api.list.and.returnValue(throwError(() => ({ status: 500 })));
      ctx.click('Atualizar consulta');
      expect(ctx.root.querySelector('.notification-list')).toBeNull();
      ctx.api.list.and.returnValue(of({ items: [item({ status: 'READ', read_at: '2026-11-09T15:01:00Z' })], next_before_id: null }));
      ctx.click('Atualizar consulta');
      expect(ctx.api.list.calls.mostRecent().args).toEqual([null]);
      expect(ctx.root.querySelector('.notification button')).toBeNull();
      expect(ctx.root.textContent).not.toContain('Carregar mais');
      expect(ctx.api.markRead).toHaveBeenCalledTimes(1);
    });
  }

  it('apresenta conflito de leitura e exige atualizar sem marcar como entregue', async () => {
    const ctx = await setup();
    ctx.api.markRead.and.returnValue(throwError(() => ({ status: 409, detail: 'A notificação ainda não foi entregue.' })));
    ctx.click('Marcar como lida');
    expect(ctx.root.textContent).toContain('A notificação ainda não foi entregue.');
    expect(ctx.root.querySelector<HTMLButtonElement>('.notification button')?.disabled).toBeTrue();
    expect(ctx.root.textContent).not.toContain('Notificação marcada como lida.');
  });
});
