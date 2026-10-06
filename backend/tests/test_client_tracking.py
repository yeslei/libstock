from datetime import date, datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.authentication import get_current_user
from app.controllers.client_tracking_controller import get_client_tracking_service
from app.controllers.circulation_controller import get_circulation_service
from app.services.client_tracking_service import ClientTrackingService
from app.models.domain import ReservationStatus


@pytest.fixture
def api():
    fake = Mock()
    fake.loans.return_value = []
    fake.reservations.return_value = []
    app.dependency_overrides[get_client_tracking_service] = lambda: fake
    app.dependency_overrides[get_circulation_service] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


@pytest.mark.parametrize('path,method', [('/api/v1/loans/me','loans'), ('/api/v1/purchase-reservations/me','reservations')])
def test_tracking_uses_authenticated_identity_even_with_tampered_query(api, path, method):
    client, fake = api
    assert client.get(path).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['SELLER'])
    assert client.get(path).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['USER'])
    response = client.get(path+'?client_id=999')
    assert response.status_code == 200
    assert response.json() == []
    getattr(fake, method).assert_called_once_with(7)


@pytest.mark.parametrize('path,payload', [
    ('/api/v1/staff/loan-requests/1/confirm-pickup', {'copy_id': 1}),
    ('/api/v1/staff/loans/1/confirm-return', None),
    ('/api/v1/staff/books/1/allocate-purchase', None),
    ('/api/v1/staff/purchase-reservations/1/confirm-sale', None),
])
def test_client_cannot_execute_staff_operations(api, path, payload):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['USER'])
    assert client.post(path, json=payload).status_code == 403


def test_loan_view_does_not_activate_pending_and_derives_overdue(monkeypatch):
    monkeypatch.setattr('app.services.client_tracking_service.business_today', lambda: date(2026,10,3))
    repo = Mock(); repo.client_exists.return_value = True
    book = NS(id=1, title='Livro', author='Autor', cover_url=None)
    repo.pending_loans.return_value = [(NS(id=11,pickup_date=date(2026,10,4)), book)]
    repo.active_loans.return_value = [
        (NS(id=21, loan_date=datetime(2026,9,1,12,tzinfo=timezone.utc), due_date=datetime(2026,10,1,12,tzinfo=timezone.utc)), NS(barcode='001'),book),
        (NS(id=22, loan_date=datetime(2026,9,3,12,tzinfo=timezone.utc), due_date=datetime(2026,10,3,12,tzinfo=timezone.utc)), NS(barcode='002'),book),
    ]
    result = ClientTrackingService(Mock(), repo).loans(7)
    assert [r.status for r in result] == ['AWAITING_PICKUP','OVERDUE','ACTIVE']
    assert result[0].due_date is None
    assert result[1].days_late == 2
    assert result[2].days_late == 0


def test_reservation_position_is_backend_value_and_no_deadline_is_invented():
    repo = Mock(); repo.client_exists.return_value = True
    repo.waiting_position.return_value = 3
    book = NS(id=1,title='Livro',author='Autor',cover_url=None)
    repo.active_reservations.return_value = [(NS(id=1,status=ReservationStatus.WAITING,notified_at=None,expires_at=None),book,None)]
    result = ClientTrackingService(Mock(),repo).reservations(7)
    assert result[0].queue_position == 3
    assert result[0].expires_at is None
    assert result[0].copy_barcode is None


@pytest.mark.parametrize('payload', [
    {'book_id': 0}, {'book_id': 2**63}, {'book_id': 1, 'client_id': 999},
    {'book_id': 1, 'status': 'NOTIFIED'}, {'book_id': 1, 'queue_position': 1},
])
def test_purchase_reservation_rejects_identity_and_state_tampering(api, payload):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['USER'])
    assert client.post('/api/v1/purchase-reservations', json=payload).status_code == 422
    fake.reserve_purchase.assert_not_called()


def test_purchase_reservation_uses_only_authenticated_identity(api):
    client, fake = api
    fake.reserve_purchase.return_value = {'id': 8, 'book_id': 2, 'status': 'WAITING', 'queue_position': 1}
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['USER'])
    assert client.post('/api/v1/purchase-reservations', json={'book_id': 2}).status_code == 201
    fake.reserve_purchase.assert_called_once_with(7, 2)


@pytest.mark.parametrize('id', [0, -1, 2**63])
def test_staff_rejects_invalid_resource_id(api, id):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['SELLER'])
    assert client.post(f'/api/v1/staff/loans/{id}/confirm-return').status_code == 422
    fake.confirm_return.assert_not_called()
