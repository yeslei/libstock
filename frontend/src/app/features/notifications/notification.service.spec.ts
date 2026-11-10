import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NotificationService } from './notification.service';

describe('Notificações: serviço', () => {
  it('pagina somente notificações próprias e marca leitura sem identidades no corpo', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const service = TestBed.inject(NotificationService);
    const http = TestBed.inject(HttpTestingController);
    service.list().subscribe();
    const first = http.expectOne((r) => r.url === '/api/v1/me/notifications');
    expect(first.request.params.get('limit')).toBe('20');
    expect(first.request.params.has('before_id')).toBeFalse();
    first.flush({ items: [], next_before_id: 30 });
    service.list(30).subscribe();
    const next = http.expectOne((r) => r.url === '/api/v1/me/notifications');
    expect(next.request.params.get('before_id')).toBe('30');
    next.flush({ items: [], next_before_id: null });
    service.markRead(8).subscribe();
    const write = http.expectOne('/api/v1/me/notifications/8/read');
    expect(write.request.method).toBe('PATCH');
    expect(write.request.body).toBeNull();
    write.flush({ id: 8, status: 'READ' });
    http.verify();
  });
});
