from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from sqlalchemy.exc import SQLAlchemyError
from app.core.exceptions import ApplicationError
from app.repositories.circulation_repository import CirculationRepository
from app.services.circulation_service import CirculationService


@pytest.fixture
def service():
    db = Mock()
    repository = Mock(spec=CirculationRepository)
    repository.is_active_employee.return_value = True
    return CirculationService(db, repository), db, repository


@pytest.mark.parametrize('method,args,lookup,code', [
    ('confirm_pickup', (1, 2, 3), 'find_request', 'loan_request_not_found'),
    ('confirm_return', (1, 3), 'find_loan', 'loan_not_found'),
    ('confirm_sale', (1, 3), 'find_reservation', 'reservation_not_found'),
    ('allocate_purchase', (1, 3), 'lock_book', 'book_not_found'),
])
def test_missing_resources_roll_back_without_success(service, method, args, lookup, code):
    instance, db, repo = service
    getattr(repo, lookup).return_value = None
    with pytest.raises(ApplicationError) as error:
        getattr(instance, method)(*args)
    assert error.value.code == code
    assert error.value.status_code == 404
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_closed_loan_cannot_be_returned_twice(service):
    instance, db, repo = service
    repo.find_loan.return_value = NS(status='RETURNED')
    with pytest.raises(ApplicationError) as error:
        instance.confirm_return(1, 3)
    assert error.value.code == 'loan_already_closed'
    db.commit.assert_not_called()


def test_query_failure_is_normalized_and_rolled_back(service):
    instance, db, repo = service
    repo.find_loan.side_effect = SQLAlchemyError('internal database details')
    with pytest.raises(ApplicationError) as error:
        instance.confirm_return(1, 3)
    assert error.value.code == 'circulation_persistence_error'
    assert 'internal database' not in error.value.message
    db.rollback.assert_called_once()


def reservation(status, client_id=5, expires_at=None):
    from app.models.domain import ReservationStatus
    return NS(id=9, book_id=1, client_id=client_id, status=ReservationStatus(status), expires_at=expires_at,
              allocated_copy_id=3)


def test_client_cannot_cancel_other_clients_reservation_and_is_not_told_it_exists(service):
    instance, db, repo = service
    repo.client_exists.return_value = True
    repo.find_reservation.return_value = reservation('WAITING', client_id=5)
    with pytest.raises(ApplicationError) as error:
        instance.cancel_own_reservation(9, 6)
    assert (error.value.code, error.value.status_code) == ('reservation_not_found', 404)
    repo.record_cancellation.assert_not_called()
    db.commit.assert_not_called()


def test_client_without_client_record_cannot_cancel(service):
    instance, db, repo = service
    repo.client_exists.return_value = False
    with pytest.raises(ApplicationError) as error:
        instance.cancel_own_reservation(9, 6)
    assert (error.value.code, error.value.status_code) == ('client_required', 403)


@pytest.mark.parametrize('status', ['FULFILLED', 'CANCELLED', 'EXPIRED'])
def test_final_reservation_cannot_be_cancelled(service, status):
    instance, db, repo = service
    repo.find_reservation.return_value = reservation(status)
    with pytest.raises(ApplicationError) as error:
        instance.cancel_reservation_by_staff(9, 3)
    assert (error.value.code, error.value.status_code, error.value.details) == (
        'reservation_not_cancellable', 409, {'status': status})
    repo.record_cancellation.assert_not_called()


def test_staff_cancel_records_actor_and_reason(service):
    instance, db, repo = service
    item = reservation('NOTIFIED', expires_at=datetime(2999, 1, 1, tzinfo=timezone.utc))
    repo.find_reservation.return_value = item
    assert instance.cancel_reservation_by_staff(9, 3, 'desistiu') == {'id': 9}
    assert item.status.value == 'CANCELLED'
    repo.record_cancellation.assert_called_once_with(9, 3, 'STAFF', 'desistiu')
    db.commit.assert_called_once()


def test_confirm_sale_after_deadline_commits_expiration_before_refusing(service):
    instance, db, repo = service
    item = reservation('NOTIFIED', expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    repo.find_reservation.return_value = item
    repo.lock_book.return_value = NS(is_active=True)
    with pytest.raises(ApplicationError) as error:
        instance.confirm_sale(9, 3)
    assert error.value.code == 'reservation_expired'
    assert item.status.value == 'EXPIRED'
    db.commit.assert_called_once()
    repo.create_sale.assert_not_called()


def test_allocation_skips_ineligible_and_sets_deadline(service, monkeypatch):
    instance, db, repo = service
    repo.lock_book.return_value = NS(is_active=True)
    first, second = reservation('WAITING', client_id=1), reservation('WAITING', client_id=2)
    first.id, second.id = 1, 2
    repo.waiting_queue.return_value = [first, second]
    repo.lock_free_copy.return_value = NS(id=77)
    monkeypatch.setattr('app.services.circulation_service.is_client_locked_eligible',
                        lambda repository, client_id, today: client_id == 2)
    assert instance.allocate_purchase(1, 3) == {'id': 2}
    assert (first.status.value, second.status.value, second.allocated_copy_id) == ('WAITING', 'NOTIFIED', 77)
    assert second.expires_at is not None and second.expires_at.hour == 23 and second.expires_at.microsecond == 999000
    repo.expire_due_reservations.assert_called_once()


def test_allocation_without_eligible_client_is_stable_conflict(service, monkeypatch):
    instance, db, repo = service
    repo.lock_book.return_value = NS(is_active=True)
    repo.waiting_queue.return_value = [reservation('WAITING')]
    monkeypatch.setattr('app.services.circulation_service.is_client_locked_eligible', lambda *a: False)
    with pytest.raises(ApplicationError) as error:
        instance.allocate_purchase(1, 3)
    assert (error.value.code, error.value.status_code) == ('no_eligible_reservation', 409)
    repo.lock_free_copy.assert_not_called()
    db.commit.assert_not_called()
