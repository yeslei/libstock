from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from app.controllers.staff_desk_controller import get_staff_desk_service
from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import ReservationStatus
from app.repositories.staff_desk_repository import StaffDeskRepository
from app.services.staff_desk_service import StaffDeskService

PATHS = ['/api/v1/staff/clients?q=ana', '/api/v1/staff/loan-requests', '/api/v1/staff/loans',
         '/api/v1/staff/purchase-reservations']
SERVICE_METHODS = ['dashboard', 'client_pendencies', 'search_clients', 'loan_requests', 'loans', 'purchase_reservations']


@pytest.fixture
def api():
    fake = Mock()
    for name in SERVICE_METHODS:
        getattr(fake, name).return_value = []
    app.dependency_overrides[get_staff_desk_service] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


@pytest.mark.parametrize('path', PATHS)
def test_requires_authentication(api, path):
    client, _ = api
    assert client.get(path).status_code == 401


@pytest.mark.parametrize('role', ['USER', 'STOCK_KEEPER'])
@pytest.mark.parametrize('path', PATHS)
def test_roles_without_counter_access_are_denied(api, path, role):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=[role])
    assert client.get(path).status_code == 403
    for name in SERVICE_METHODS:
        getattr(fake, name).assert_not_called()


@pytest.mark.parametrize('role', ['SELLER', 'ADMINISTRATOR'])
@pytest.mark.parametrize('path', PATHS)
def test_counter_roles_can_read(api, path, role):
    client, _ = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=[role])
    response = client.get(path)
    assert response.status_code == 200 and response.json() == []


@pytest.mark.parametrize('path', [
    '/api/v1/staff/clients', '/api/v1/staff/clients?q=a', '/api/v1/staff/clients?q=' + 'x' * 101,
    '/api/v1/staff/clients?q=ana&limit=0', '/api/v1/staff/loans?limit=101', '/api/v1/staff/loans?client_id=0',
    '/api/v1/staff/loans?client_id=abc', '/api/v1/staff/loan-requests?client_id=2147483648',
    '/api/v1/staff/purchase-reservations?status=FULFILLED', '/api/v1/staff/loans?q=' + 'x' * 101,
])
def test_invalid_query_is_rejected(api, path):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['SELLER'])
    assert client.get(path).status_code == 422
    for name in SERVICE_METHODS:
        getattr(fake, name).assert_not_called()


def test_filters_and_actor_are_forwarded(api):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['SELLER'])
    client.get('/api/v1/staff/loans?q=dom&client_id=5&limit=10')
    fake.loans.assert_called_once_with(7, 'dom', 5, 10)
    client.get('/api/v1/staff/purchase-reservations?status=WAITING')
    fake.purchase_reservations.assert_called_once_with(7, None, None, 'WAITING', 50)


def make_service():
    repo = Mock(spec=StaffDeskRepository)
    repo.is_active_employee.return_value = True
    return StaffDeskService(Mock(), repo), repo


def client_row(**over):
    row = dict(client_id=3, client_name='Ana', client_email='ana@x.test', profile_active=True, user_active=True,
               client_penalized=False, has_overdue_loan=False)
    row.update(over)
    return row


@pytest.mark.parametrize('method,args', [
    ('search_clients', ('ana', 7, 20)), ('loan_requests', (7, None, None, 50)), ('loans', (7, None, None, 50)),
    ('purchase_reservations', (7, None, None, None, 50)),
])
def test_inactive_employee_is_denied_without_querying(method, args):
    service, repo = make_service()
    repo.is_active_employee.return_value = False
    with pytest.raises(ApplicationError) as error:
        getattr(service, method)(*args)
    assert (error.value.status_code, error.value.code) == (403, 'employee_record_required')
    repo.search_clients.assert_not_called()
    repo.pending_loan_requests.assert_not_called()
    repo.open_loans.assert_not_called()
    repo.active_reservations.assert_not_called()


@pytest.mark.parametrize('term', [None, '', ' a ', '   '])
def test_client_search_requires_minimum_term(term):
    service, repo = make_service()
    with pytest.raises(ApplicationError) as error:
        service.search_clients(term, 7, 20)
    assert (error.value.status_code, error.value.code) == (422, 'search_term_too_short')
    repo.search_clients.assert_not_called()


def test_client_search_flags_ineligible_clients_and_trims_term():
    service, repo = make_service()
    repo.search_clients.return_value = [client_row(), client_row(client_id=4, client_penalized=True),
                                        client_row(client_id=5, has_overdue_loan=True),
                                        client_row(client_id=6, user_active=False)]
    result = service.search_clients('  ana ', 7, 20)
    assert repo.search_clients.call_args.args[0] == 'ana'
    assert [c.eligible for c in result] == [True, False, False, False]
    assert result[3].is_active is False
    assert set(result[0].model_dump()) == {'id', 'name', 'email', 'is_active', 'is_penalized', 'has_overdue_loan', 'eligible'}


def test_loan_requests_only_offer_copies_for_active_books():
    service, repo = make_service()
    active = NS(id=1, title='A', author='X', is_active=True)
    inactive = NS(id=2, title='B', author='Y', is_active=False)
    stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def request(id, book):
        return {'LoanRequest': NS(id=id, pickup_date=date(2026, 10, 5), due_date=date(2026, 11, 5), created_at=stamp),
                'Book': book, **client_row()}
    repo.pending_loan_requests.return_value = [request(10, active), request(11, inactive)]
    repo.eligible_didactic_copies.return_value = [NS(id=5, book_id=1, barcode='B1', condition='GOOD')]
    result = service.loan_requests(7, ' ', None, 50)
    assert repo.pending_loan_requests.call_args.args[0] is None
    repo.eligible_didactic_copies.assert_called_once_with([1])
    assert [len(item.eligible_copies) for item in result] == [1, 0]
    assert result[0].eligible_copies[0].barcode == 'B1'


def test_loans_compute_delay_with_business_date(monkeypatch):
    service, repo = make_service()
    monkeypatch.setattr('app.services.staff_desk_service.business_today', lambda: date(2026, 10, 3))
    book = NS(id=1, title='A', author='X', is_active=True)

    def loan(id, due):
        return {'Loan': NS(id=id, loan_date=due - timedelta(days=30), due_date=due),
                'Copy': NS(id=id, barcode=f'C{id}'), 'Book': book, **client_row()}
    repo.open_loans.return_value = [loan(1, datetime(2026, 10, 1, 12, tzinfo=timezone.utc)),
                                    loan(2, datetime(2026, 10, 3, 12, tzinfo=timezone.utc))]
    result = service.loans(7, None, None, 50)
    assert [(i.status, i.days_late) for i in result] == [('OVERDUE', 2), ('ACTIVE', 0)]


def reservation_row(id, status, position, *, client=None, book=None, barcode=None, **fields):
    reservation = NS(id=id, status=status, requested_at=datetime(2026, 10, 1, tzinfo=timezone.utc), notified_at=None,
                     expires_at=None, allocated_copy_id=None)
    for key, value in fields.items():
        setattr(reservation, key, value)
    return {'PurchaseReservation': reservation, 'Book': book or NS(id=1, title='A', author='X', is_active=True),
            'allocated_barcode': barcode, 'pickup_date': None, 'waiting_position': position,
            **(client or client_row())}


INACTIVE_BOOK = NS(id=1, title='A', author='X', is_active=False)


@pytest.mark.parametrize('row,free,expected', [
    (reservation_row(1, ReservationStatus.WAITING, 1), 1, (True, None)),
    (reservation_row(1, ReservationStatus.WAITING, 1), 0, (False, 'NO_FREE_COPY')),
    (reservation_row(1, ReservationStatus.WAITING, 1, client=client_row(client_penalized=True)), 1, (False, 'CLIENT_INELIGIBLE')),
    (reservation_row(1, ReservationStatus.WAITING, 2), 1, (False, 'NOT_FIRST_IN_QUEUE')),
    (reservation_row(1, ReservationStatus.WAITING, 1, book=INACTIVE_BOOK), 1, (False, 'BOOK_INACTIVE')),
])
def test_allocation_flags_follow_service_rules_without_skipping_queue(row, free, expected):
    service, repo = make_service()
    repo.active_reservations.return_value = [row]
    repo.free_commercial_counts.return_value = {1: free} if free else {}
    item = service.purchase_reservations(7, None, None, None, 50)[0]
    assert (item.can_allocate, item.allocation_blocked_reason) == expected
    assert item.free_commercial_copies == free


def test_notified_reservation_exposes_allocation_without_inventing_deadline():
    service, repo = make_service()
    repo.active_reservations.return_value = [reservation_row(
        1, ReservationStatus.NOTIFIED, None, allocated_copy_id=9, barcode='C9', notified_at=datetime.now(timezone.utc))]
    repo.free_commercial_counts.return_value = {}
    item = service.purchase_reservations(7, None, None, 'NOTIFIED', 50)[0]
    assert repo.active_reservations.call_args.args[2] == ReservationStatus.NOTIFIED
    assert (item.queue_position, item.allocated_copy_barcode, item.expires_at, item.expired, item.can_allocate) == (
        None, 'C9', None, False, False)


def test_expired_allocation_is_flagged():
    service, repo = make_service()
    repo.active_reservations.return_value = [reservation_row(
        1, ReservationStatus.NOTIFIED, None, allocated_copy_id=9, expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc))]
    repo.free_commercial_counts.return_value = {}
    assert service.purchase_reservations(7, None, None, None, 50)[0].expired is True


def test_query_failure_is_normalized():
    service, repo = make_service()
    repo.open_loans.side_effect = SQLAlchemyError('internal database details')
    with pytest.raises(ApplicationError) as error:
        service.loans(7, None, None, 50)
    assert (error.value.status_code, error.value.code) == (500, 'desk_query_error')
    assert 'internal database' not in error.value.message


PEND = '/api/v1/staff/clients/3/pendencies'


def test_pendencies_requires_auth_and_staff_role(api):
    client, fake = api
    assert client.get(PEND).status_code == 401
    for role in ('USER', 'STOCK_KEEPER'):
        app.dependency_overrides[get_current_user] = lambda role=role: NS(id=7, role_codes=[role])
        assert client.get(PEND).status_code == 403
    fake.client_pendencies.assert_not_called()


@pytest.mark.parametrize('id', [0, -1, 2147483648, 'abc'])
def test_pendencies_rejects_invalid_id(api, id):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['SELLER'])
    assert client.get(f'/api/v1/staff/clients/{id}/pendencies').status_code == 422
    fake.client_pendencies.assert_not_called()


def test_pendencies_forwards_actor_and_client(api):
    client, fake = api
    fake.client_pendencies.return_value = {
        'client': {'id': 3, 'name': 'Ana', 'email': 'a@x.test', 'is_active': True, 'is_penalized': False,
                   'has_overdue_loan': False, 'eligible': True},
        'overdue_loans': []}
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['ADMINISTRATOR'])
    response = client.get(PEND)
    assert response.status_code == 200 and response.json()['client']['id'] == 3
    fake.client_pendencies.assert_called_once_with(7, 3)


def test_pendencies_service_denies_inactive_employee_and_missing_client():
    service, repo = make_service()
    repo.is_active_employee.return_value = False
    with pytest.raises(ApplicationError) as error:
        service.client_pendencies(7, 3)
    assert error.value.code == 'employee_record_required'
    repo.client_summary.assert_not_called()
    repo.is_active_employee.return_value = True
    repo.client_summary.return_value = None
    with pytest.raises(ApplicationError) as error:
        service.client_pendencies(7, 3)
    assert (error.value.status_code, error.value.code) == (404, 'client_not_found')


def test_pendencies_lists_only_overdue_loans_and_never_writes(monkeypatch):
    service, repo = make_service()
    monkeypatch.setattr('app.services.staff_desk_service.business_today', lambda: date(2026, 10, 3))
    book = NS(id=1, title='A', author='X', is_active=True)
    repo.client_summary.return_value = client_row(has_overdue_loan=True)

    def loan(id, due):
        return {'Loan': NS(id=id, loan_date=due - timedelta(days=30), due_date=due),
                'Copy': NS(id=id, barcode=f'C{id}'), 'Book': book, **client_row()}
    repo.open_loans.return_value = [loan(1, datetime(2026, 10, 1, 12, tzinfo=timezone.utc)),
                                    loan(2, datetime(2026, 10, 3, 6, tzinfo=timezone.utc))]
    result = service.client_pendencies(7, 3)
    assert [(l.id, l.days_late) for l in result.overdue_loans] == [(1, 2)]
    assert result.client.eligible is False
    service.db.commit.assert_not_called()


def test_dashboard_requires_authentication_and_staff_role(api):
    client, fake = api
    assert client.get('/api/v1/staff/dashboard').status_code == 401
    for role in ('USER', 'STOCK_KEEPER'):
        app.dependency_overrides[get_current_user] = lambda role=role: NS(id=7, role_codes=[role])
        assert client.get('/api/v1/staff/dashboard').status_code == 403
    fake.dashboard.assert_not_called()


@pytest.mark.parametrize('role', ['SELLER', 'ADMINISTRATOR'])
def test_dashboard_returns_explicit_schema(api, role):
    client, fake = api
    fake.dashboard.return_value = {'active_loans': 3, 'returns_today': 2, 'waiting_reservations': 1, 'pendencies': 4}
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=[role])
    response = client.get('/api/v1/staff/dashboard')
    assert response.status_code == 200
    assert response.json() == {'active_loans': 3, 'returns_today': 2, 'waiting_reservations': 1, 'pendencies': 4}
    fake.dashboard.assert_called_once_with(7)


def test_dashboard_denies_inactive_employee_without_querying():
    service, repo = make_service()
    repo.is_active_employee.return_value = False
    with pytest.raises(ApplicationError) as error:
        service.dashboard(7)
    assert (error.value.status_code, error.value.code) == (403, 'employee_record_required')
    repo.dashboard_counts.assert_not_called()


def test_dashboard_uses_sao_paulo_day_window(monkeypatch):
    service, repo = make_service()
    monkeypatch.setattr('app.services.staff_desk_service.business_today', lambda: date(2026, 10, 3))
    repo.dashboard_counts.return_value = {'active_loans': 1, 'returns_today': 0, 'waiting_reservations': 2, 'pendencies': 0}
    result = service.dashboard(7)
    cutoff, next_cutoff = repo.dashboard_counts.call_args.args
    assert cutoff.isoformat() == '2026-10-03T00:00:00-03:00' and next_cutoff.isoformat() == '2026-10-04T00:00:00-03:00'
    assert result.model_dump() == {'active_loans': 1, 'returns_today': 0, 'waiting_reservations': 2, 'pendencies': 0}


def test_dashboard_database_failure_is_500():
    service, repo = make_service()
    repo.dashboard_counts.side_effect = SQLAlchemyError('boom')
    with pytest.raises(ApplicationError) as error:
        service.dashboard(7)
    assert (error.value.status_code, error.value.code) == (500, 'desk_query_error')
