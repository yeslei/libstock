from datetime import date, datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient
from app.core.exceptions import ApplicationError
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


@pytest.fixture
def reservation_service():
    repo = Mock()
    repo.lock_book.return_value = NS(id=2, is_active=True)
    repo.lock_client.return_value = (NS(is_penalized=False), NS(is_active=True), NS(is_active=True))
    repo.has_overdue_loan.return_value = False
    repo.existing_reservation.return_value = None
    repo.has_waiting_queue.return_value = False
    repo.has_reservable_commercial_copy.return_value = True
    repo.has_free_commercial_copy.return_value = False
    repo.waiting_position.return_value = 1
    repo.create_reservation.return_value = NS(id=8, book_id=2, status='WAITING', queue_position=1)
    db = Mock()
    return ClientTrackingService(db, repo), db, repo


def test_purchase_reservation_persists_for_eligible_client(reservation_service):
    service, db, repo = reservation_service
    response = service.reserve_purchase(7, 2)
    repo.create_reservation.assert_called_once_with(7, 2)
    db.commit.assert_called_once()
    assert (response.id, response.book_id, response.status, response.queue_position) == (8, 2, 'WAITING', 1)


@pytest.mark.parametrize('condition', ['penalized', 'inactive_profile', 'inactive_user', 'overdue'])
def test_purchase_reservation_refuses_ineligible_client(reservation_service, condition):
    service, db, repo = reservation_service
    client, profile, user = repo.lock_client.return_value
    if condition == 'penalized':
        client.is_penalized = True
    elif condition == 'inactive_profile':
        profile.is_active = False
    elif condition == 'inactive_user':
        user.is_active = False
    else:
        repo.has_overdue_loan.return_value = True

    with pytest.raises(ApplicationError) as error:
        service.reserve_purchase(7, 2)

    assert (error.value.status_code, error.value.code) == (403, 'client_ineligible')
    repo.create_reservation.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize('case,status,code', [
    ('no_client', 403, 'client_required'),
    ('book_missing', 404, 'book_not_found'),
    ('book_inactive', 404, 'book_not_found'),
    ('duplicate', 409, 'reservation_duplicate'),
    ('unavailable', 409, 'reservation_unavailable'),
    ('purchase_available', 409, 'purchase_available'),
])
def test_purchase_reservation_rejects_inconsistent_state(reservation_service, case, status, code):
    service, db, repo = reservation_service
    if case == 'no_client':
        repo.lock_client.return_value = None
    elif case == 'book_missing':
        repo.lock_book.return_value = None
    elif case == 'book_inactive':
        repo.lock_book.return_value.is_active = False
    elif case == 'duplicate':
        repo.existing_reservation.return_value = NS(id=1)
    elif case == 'unavailable':
        repo.has_reservable_commercial_copy.return_value = False
    else:
        repo.has_free_commercial_copy.return_value = True

    with pytest.raises(ApplicationError) as error:
        service.reserve_purchase(7, 2)

    assert (error.value.status_code, error.value.code) == (status, code)
    repo.create_reservation.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_purchase_reservation_commit_failure_rolls_back(reservation_service):
    service, db, repo = reservation_service
    db.commit.side_effect = SQLAlchemyError('failure')

    with pytest.raises(ApplicationError) as error:
        service.reserve_purchase(7, 2)

    assert (error.value.status_code, error.value.code) == (500, 'reservation_persistence_error')
    repo.create_reservation.assert_called_once_with(7, 2)
    db.rollback.assert_called_once()


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
