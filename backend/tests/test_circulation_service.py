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
