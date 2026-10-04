from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.controllers.purchase_request_controller import get_purchase_request_service
from app.dependencies.authentication import get_current_user
from app.core.exceptions import ApplicationError
from app.schemas.purchase_request_schema import PurchaseRequestCreate
from app.services.purchase_request_service import PurchaseRequestService
from test_loan_requests import setup_service


@pytest.fixture
def purchase(setup_service, monkeypatch):
    _, db, repo = setup_service
    monkeypatch.setattr('app.services.purchase_request_service.business_today', lambda: date(2026, 10, 3))
    repo.has_waiting_queue = Mock(return_value=False)
    repo.has_queueable_commercial_copy = Mock(return_value=True)
    return PurchaseRequestService(db, repo), db, repo


def test_purchase_success_persists_authenticated_client(purchase):
    service, db, repo = purchase
    response = service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 3)), client_id=7)
    repo.create.assert_called_once()
    assert repo.create.call_args.args == (7, 10, date(2026, 10, 3), 10)
    db.commit.assert_called_once()
    assert response.status == 'PENDING'


@pytest.mark.parametrize('case,status,code', [
    ('no_client', 403, 'client_required'), ('penalized', 403, 'client_ineligible'),
    ('inactive', 403, 'client_ineligible'), ('missing_book', 404, 'book_not_found'),
    ('duplicate', 409, 'purchase_request_duplicate'), ('unavailable', 409, 'purchase_unavailable'),
])
def test_purchase_rejects_conditions(purchase, case, status, code):
    service, db, repo = purchase
    if case == 'no_client': repo.lock_client.return_value = None
    if case == 'penalized': repo.lock_client.return_value[0].is_penalized = True
    if case == 'inactive': repo.lock_client.return_value[1].is_active = False
    if case == 'missing_book': repo.lock_book.return_value = None
    if case == 'duplicate': repo.find_pending.return_value = 1
    if case == 'unavailable': repo.lock_available_copy.return_value = None
    with pytest.raises(ApplicationError) as error:
        service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 3)), client_id=7)
    assert (error.value.status_code, error.value.code) == (status, code)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_purchase_commit_failure_rolls_back(purchase):
    service, db, repo = purchase
    db.commit.side_effect = SQLAlchemyError('failure')
    with pytest.raises(ApplicationError) as error:
        service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 3)), client_id=7)
    assert error.value.status_code == 500
    db.rollback.assert_called_once()


def test_purchase_api_contract_and_access(purchase):
    service, _, _ = purchase
    app.dependency_overrides[get_purchase_request_service] = lambda: service
    client = TestClient(app)
    payload = {'book_id': 10, 'pickup_date': '2026-10-03'}
    try:
        assert client.post('/api/v1/purchase-requests', json=payload).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=['SELLER'])
        assert client.post('/api/v1/purchase-requests', json=payload).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=['USER'])
        assert client.post('/api/v1/purchase-requests', json=payload | {'client_id': 99}).status_code == 422
        assert client.post('/api/v1/purchase-requests', json=payload).status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_repository_create_sets_pickup_deadline_for_new_notified_reservation():
    from unittest.mock import Mock
    from app.core.business_dates import reservation_pickup_deadline
    from app.repositories.purchase_request_repository import PurchaseRequestRepository
    db = Mock()
    PurchaseRequestRepository(db).create(1, 2, __import__('datetime').date(2026, 10, 4), 9)
    reservation = db.add.call_args_list[0].args[0]
    assert reservation.status.value == 'NOTIFIED'
    assert reservation.expires_at == reservation_pickup_deadline(reservation.notified_at)


def test_purchase_born_notified_returns_reservation_status(purchase):
    service, _, _ = purchase
    assert service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 3)), client_id=7).reservation_status == 'NOTIFIED'


def test_pickup_date_after_the_reservation_deadline_is_refused(purchase, monkeypatch):
    from datetime import datetime
    service, db, repo = purchase
    monkeypatch.setattr('app.services.purchase_request_service.datetime',
                        Mock(now=lambda zone: datetime(2026, 10, 3, 12, 0, tzinfo=zone)))
    service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 8)), client_id=7)  # último dia do prazo
    repo.create.reset_mock(); db.rollback.reset_mock()
    with pytest.raises(ApplicationError) as error:
        service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 9)), client_id=7)
    assert (error.value.status_code, error.value.code) == (422, 'pickup_date_after_deadline')
    repo.create.assert_not_called()
    db.rollback.assert_called_once()


def test_purchase_with_waiting_queue_joins_the_end_of_the_queue_even_with_a_free_copy(purchase):
    service, _, repo = purchase
    repo.has_waiting_queue.return_value = True
    response = service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 12, 25)), client_id=7)
    assert repo.create.call_args.args == (7, 10, date(2026, 12, 25), None)  # sem exemplar: reserva WAITING
    repo.lock_available_copy.assert_not_called()
    assert response.reservation_status == 'WAITING'  # data além do prazo é aceita: ainda não há destinação


def test_purchase_with_waiting_queue_needs_a_serviceable_copy(purchase):
    service, db, repo = purchase
    repo.has_waiting_queue.return_value = True
    repo.has_queueable_commercial_copy.return_value = False
    with pytest.raises(ApplicationError) as error:
        service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 3)), client_id=7)
    assert (error.value.status_code, error.value.code) == (409, 'purchase_unavailable')
    repo.create.assert_not_called()


def test_repository_create_without_copy_is_a_waiting_reservation_without_deadline():
    from app.repositories.purchase_request_repository import PurchaseRequestRepository
    db = Mock()
    PurchaseRequestRepository(db).create(1, 2, date(2026, 10, 4))
    reservation = db.add.call_args_list[0].args[0]
    assert (reservation.status.value, reservation.allocated_copy_id, reservation.notified_at, reservation.expires_at) == (
        'WAITING', None, None, None)
