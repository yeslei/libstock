"""Prazo de um mês e atraso por data de São Paulo em todos os fluxos (Issue #148), contra PostgreSQL descartável."""
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.business_dates import BUSINESS_ZONE, loan_due_at
from app.core.exceptions import ClientHasPendingError, CopyNotForLoanError
from app.models.domain import Client, Loan, LoanStatus
from app.repositories.client_pendency_repository import ClientPendencyRepository
from app.repositories.loan_repository import LoanRepository
from app.schemas.loan_schema import LoanCreate
from app.services.client_pendency_service import ClientPendencyService
from app.services.loan_service import LoanService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import commercial_copy, desk, didactic_copy  # noqa: F401  (fixtures)


def loan_service(db):
    return LoanService(LoanRepository(db), db, ClientPendencyService(db, ClientPendencyRepository(db)))


def test_direct_loan_due_is_one_calendar_month_in_sao_paulo(desk):  # noqa: F811
    _, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        copy_id = didactic_copy(db, book_id).id
        result = loan_service(db).create_loan(LoanCreate(client_id=client_id, copy_id=copy_id), employee_id=seller_id)
        assert result.due_date == loan_due_at(result.loan_date)
        assert result.due_date.astimezone(BUSINESS_ZONE).date() >= result.loan_date.astimezone(BUSINESS_ZONE).date() + timedelta(days=28)


def test_direct_loan_rejects_commercial_copy_without_writing(desk):  # noqa: F811
    _, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        copy_id = commercial_copy(db, book_id).id
        with pytest.raises(CopyNotForLoanError) as error:
            loan_service(db).create_loan(LoanCreate(client_id=client_id, copy_id=copy_id), employee_id=seller_id)
        assert (error.value.status_code, error.value.code) == (409, 'copy_not_for_loan')
    with Session(engine) as db:
        assert db.query(Loan).filter(Loan.client_id == client_id).count() == 0


def _open_loan(engine, book_id, client_id, seller_id, due):
    with Session(engine) as db:
        db.add(Loan(client_id=client_id, copy_id=didactic_copy(db, book_id).id, employee_id=seller_id,
                    loan_date=due - timedelta(days=30), due_date=due, status=LoanStatus.OPEN))
        db.commit()


def test_due_today_earlier_is_not_overdue_in_v1_pendencies_sync_or_direct_loan(desk):  # noqa: F811
    _, engine, book_id, client_id, seller_id = desk
    today = datetime.now(BUSINESS_ZONE).date()
    _open_loan(engine, book_id, client_id, seller_id, datetime.combine(today, time(0, 1), BUSINESS_ZONE))
    with Session(engine) as db:
        service = ClientPendencyService(db, ClientPendencyRepository(db))
        response = service.get_pendencies(client_id)
        assert response.overdue_loans == [] and response.is_penalized is False
        assert db.get(Client, client_id).is_penalized is False
        assert service.validate_client_for_operation(client_id).valid is True


def test_due_yesterday_is_overdue_in_v1_pendencies_sync_and_blocks_direct_loan(desk):  # noqa: F811
    _, engine, book_id, client_id, seller_id = desk
    today = datetime.now(BUSINESS_ZONE).date()
    _open_loan(engine, book_id, client_id, seller_id, datetime.combine(today - timedelta(days=1), time(23, 59), BUSINESS_ZONE))
    with Session(engine) as db:
        response = ClientPendencyService(db, ClientPendencyRepository(db)).get_pendencies(client_id)
        assert len(response.overdue_loans) == 1 and response.is_penalized is True
        assert db.get(Client, client_id).is_penalized is True
    with Session(engine) as db:
        copy_id = commercial_copy(db, book_id).id
        with pytest.raises(ClientHasPendingError):
            loan_service(db).create_loan(LoanCreate(client_id=client_id, copy_id=copy_id), employee_id=seller_id)
