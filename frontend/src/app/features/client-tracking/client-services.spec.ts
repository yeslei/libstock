import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ClientRequestsService } from './client-requests.service';
import { ClientTrackingService } from './client-tracking.service';

describe('Client V2 API contracts', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('queries tracking through /me without accepting another client ID', () => {
    const service = TestBed.inject(ClientTrackingService);
    service.getLoans().subscribe();
    service.getReservations().subscribe();
    for (const url of ['/api/v1/loans/me', '/api/v1/purchase-reservations/me']) {
      const request = http.expectOne(url);
      expect(request.request.method).toBe('GET');
      expect(request.request.params.keys()).toEqual([]);
      request.flush([]);
    }
  });

  it('sends only book and pickup date for a loan request', () => {
    TestBed.inject(ClientRequestsService).requestLoan(42, '2026-10-04').subscribe();
    const request = http.expectOne('/api/v1/loan-requests');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ book_id: 42, pickup_date: '2026-10-04' });
    request.flush({});
  });

  it('uses the purchase request and queue reservation endpoints separately', () => {
    const service = TestBed.inject(ClientRequestsService);
    service.requestPurchase(42, '2026-10-04').subscribe();
    service.reservePurchase(42).subscribe();
    const purchase = http.expectOne('/api/v1/purchase-requests');
    const reservation = http.expectOne('/api/v1/purchase-reservations');
    expect(purchase.request.body).toEqual({ book_id: 42, pickup_date: '2026-10-04' });
    expect(reservation.request.body).toEqual({ book_id: 42 });
    purchase.flush({}); reservation.flush({});
  });

  it("cancels only the own reservation through the /me-scoped route without a body", () => {
    TestBed.inject(ClientTrackingService).cancelReservation(7).subscribe();
    const request = http.expectOne("/api/v1/purchase-reservations/7/cancel");
    expect(request.request.method).toBe("POST");
    expect(request.request.body).toEqual({});
    request.flush({ id: 7 });
  });
});
