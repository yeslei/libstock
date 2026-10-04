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
    return PurchaseRequestService(db, repo), db, repo


def test_purchase_success_persists_authenticated_client(purchase):
    service, db, repo = purchase
    response = service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 31)), client_id=7)
    repo.create.assert_called_once_with(7, 10, date(2026, 10, 31), 10)
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
        service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 31)), client_id=7)
    assert (error.value.status_code, error.value.code) == (status, code)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_purchase_commit_failure_rolls_back(purchase):
    service, db, repo = purchase
    db.commit.side_effect = SQLAlchemyError('failure')
    with pytest.raises(ApplicationError) as error:
        service.create(PurchaseRequestCreate(book_id=10, pickup_date=date(2026, 10, 31)), client_id=7)
    assert error.value.status_code == 500
    db.rollback.assert_called_once()


def test_purchase_api_contract_and_access(purchase):
    service, _, _ = purchase
    app.dependency_overrides[get_purchase_request_service] = lambda: service
    client = TestClient(app)
    payload = {'book_id': 10, 'pickup_date': '2026-10-31'}
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
