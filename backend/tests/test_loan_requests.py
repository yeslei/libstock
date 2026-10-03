from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.controllers.loan_request_controller import get_loan_request_service
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_catalog_service
from app.core.exceptions import ApplicationError
from app.repositories.loan_request_repository import LoanRequestRepository
from app.schemas.loan_request_schema import LoanRequestCreate
from app.services.loan_request_service import LoanRequestService, next_month


@pytest.fixture
def setup_service(monkeypatch):
    monkeypatch.setattr('app.services.loan_request_service.business_today', lambda: date(2026, 10, 3))
    db = Mock()
    repository = Mock(spec=LoanRequestRepository)
    repository.lock_client.return_value = (SimpleNamespace(is_penalized=False), SimpleNamespace(is_active=True), SimpleNamespace(is_active=True))
    repository.has_overdue_loan.return_value = False
    repository.lock_book.return_value = SimpleNamespace(is_active=True)
    repository.find_pending.return_value = None
    repository.lock_available_copy.return_value = SimpleNamespace(id=10)
    repository.create.return_value = SimpleNamespace(id=1, book_id=10, pickup_date=date(2026, 10, 31),
                                                     due_date=date(2026, 11, 30), status='PENDING', created_at=datetime.now(timezone.utc))
    return LoanRequestService(db, repository), db, repository


@pytest.mark.parametrize('pickup,expected', [
    (date(2026, 1, 31), date(2026, 2, 28)), (date(2028, 1, 31), date(2028, 2, 29)),
    (date(2026, 12, 31), date(2027, 1, 31)), (date(2026, 10, 3), date(2026, 11, 3)),
])
def test_calendar_month(pickup, expected):
    assert next_month(pickup) == expected


def test_request_is_persisted_with_authenticated_client_and_server_due_date(setup_service):
    service, db, repository = setup_service
    result = service.create(LoanRequestCreate(book_id=10, pickup_date=date(2026, 10, 31)), client_id=7)
    repository.create.assert_called_once_with(7, 10, date(2026, 10, 31), date(2026, 11, 30))
    db.commit.assert_called_once()
    assert result.status == 'PENDING'


@pytest.mark.parametrize('case,code,status', [
    ('no_client', 'client_required', 403), ('penalized', 'client_ineligible', 403),
    ('inactive_profile', 'client_ineligible', 403), ('inactive_user', 'client_ineligible', 403),
    ('missing_book', 'book_not_found', 404), ('inactive_book', 'book_not_found', 404),
    ('duplicate', 'loan_request_duplicate', 409), ('unavailable', 'loan_unavailable', 409),
])
def test_request_rejects_invalid_conditions(setup_service, case, code, status):
    service, db, repo = setup_service
    if case == 'no_client': repo.lock_client.return_value = None
    if case == 'penalized': repo.lock_client.return_value[0].is_penalized = True
    if case == 'inactive_profile': repo.lock_client.return_value[1].is_active = False
    if case == 'inactive_user': repo.lock_client.return_value[2].is_active = False
    if case == 'missing_book': repo.lock_book.return_value = None
    if case == 'inactive_book': repo.lock_book.return_value.is_active = False
    if case == 'duplicate': repo.find_pending.return_value = 9
    if case == 'unavailable': repo.lock_available_copy.return_value = None
    with pytest.raises(ApplicationError) as error:
        service.create(LoanRequestCreate(book_id=10, pickup_date=date(2026, 10, 31)), client_id=7)
    assert (error.value.code, error.value.status_code) == (code, status)
    repo.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_past_date_rejected(setup_service):
    service, db, repo = setup_service
    with pytest.raises(ApplicationError) as error:
        service.create(LoanRequestCreate(book_id=10, pickup_date=date(2026, 10, 2)), client_id=7)
    assert error.value.code == 'invalid_pickup_date'
    repo.create.assert_not_called()


def test_failed_commit_rolls_back_without_success(setup_service):
    service, db, repo = setup_service
    db.commit.side_effect = SQLAlchemyError('failure')
    with pytest.raises(ApplicationError) as error:
        service.create(LoanRequestCreate(book_id=10, pickup_date=date(2026, 10, 31)), client_id=7)
    assert error.value.status_code == 500
    db.rollback.assert_called_once()


@pytest.fixture
def api(setup_service):
    service, _, _ = setup_service
    app.dependency_overrides[get_loan_request_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def authenticate(role='USER'):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=[role])


def test_api_requires_authentication(api):
    assert api.post('/api/v1/loan-requests', json={'book_id': 10, 'pickup_date': '2026-10-31'}).status_code == 401


def test_api_requires_client_role(api):
    authenticate('SELLER')
    assert api.post('/api/v1/loan-requests', json={'book_id': 10, 'pickup_date': '2026-10-31'}).status_code == 403


def test_api_success(api):
    authenticate()
    response = api.post('/api/v1/loan-requests', json={'book_id': 10, 'pickup_date': '2026-10-31'})
    assert response.status_code == 201
    assert response.json()['due_date'] == '2026-11-30'


@pytest.mark.parametrize('payload', [
    {'book_id': -1, 'pickup_date': '2026-10-31'}, {'book_id': 10, 'pickup_date': 'invalid'},
    {'book_id': 10, 'pickup_date': '2026-10-31', 'client_id': 99},
    {'book_id': 10, 'pickup_date': '2026-10-31', 'due_date': '2027-10-31'},
])
def test_api_input_and_identity_cannot_be_overridden(api, payload):
    authenticate()
    assert api.post('/api/v1/loan-requests', json=payload).status_code == 422


def test_public_details_not_found(api):
    fake = Mock()
    fake.get_public_book.side_effect = ApplicationError('Obra não encontrada.', 'book_not_found', 404)
    app.dependency_overrides[get_catalog_service] = lambda: fake
    response = api.get('/api/v1/catalog/books/999')
    assert response.status_code == 404


def test_public_details_returns_modalities_without_client_identity(api):
    from app.services.catalog_service import CatalogService
    from app.models.domain import CopyStatus, DestinationType
    book = SimpleNamespace(id=10, title='Livro', author='Autor', cover_url=None, genres=[], isbn='9788535914849', copies=[])
    repo = Mock()
    repo.find_public_book.return_value = book
    repo.find_free_copies.return_value = [SimpleNamespace(id=1, destination=DestinationType.DIDACTIC)]
    repo.find_reservable_copy_ids.return_value = set()
    service = CatalogService(db=Mock(), catalog_repository=repo, genre_repository=Mock())
    app.dependency_overrides[get_catalog_service] = lambda: service
    response = api.get('/api/v1/catalog/books/10')
    assert response.status_code == 200
    assert response.json()['availability']['loan']['available_count'] == 1
    assert response.json()['availability']['sale']['available'] is False
    assert response.json()['availability']['local_consultation']['configured'] is False
