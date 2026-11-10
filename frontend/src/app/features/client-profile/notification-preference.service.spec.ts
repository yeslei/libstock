import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NotificationPreferenceService } from './notification-preference.service';

describe('Preferência de notificações: serviço', () => {
  it('consulta e altera apenas o canal do próprio cliente', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const service = TestBed.inject(NotificationPreferenceService);
    const http = TestBed.inject(HttpTestingController);
    service.get().subscribe((result) => expect(result.channel).toBe('IN_APP'));
    http.expectOne('/api/v1/me/notification-preferences').flush({ channel: 'IN_APP', email: 'client@example.com' });
    service.update('EMAIL').subscribe((result) => expect(result.channel).toBe('EMAIL'));
    const request = http.expectOne('/api/v1/me/notification-preferences');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ channel: 'EMAIL' });
    request.flush({ channel: 'EMAIL', email: 'client@example.com' });
    http.verify();
  });
});
